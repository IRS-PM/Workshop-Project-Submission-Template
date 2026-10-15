import type {
  AllergenCode,
  DietaryCode,
  NutrientCode,
  PlanMeal,
  PlanRequest,
  PlanResponse,
} from "@/lib/plan-api";

export type Constraints = {
  dietary: DietaryCode[];
  allergies: AllergenCode[];
  goals: Partial<Record<NutrientCode, number>>;
};

export type PromptReading = {
  found: Constraints;
  unsupported: string[];
  reset: boolean;
  understood: boolean;
};

export const NO_CONSTRAINTS: Constraints = { dietary: [], allergies: [], goals: {} };

const UNITS: Record<NutrientCode, string> = {
  calories: "kcal", protein: "g", carbs: "g", fat: "g", saturated_fat: "g",
  fiber: "g", sugar: "g", sodium: "mg", cholesterol: "mg",
};

const DIETARY_WORDS: [RegExp, DietaryCode][] = [
  [/\b(?:vegetarian|veggie|vegan|meat[- ]?free|meatless|plant[- ]?(?:based|powered)?)\b/, "vegetarian"],
  [/\bhalal\b/, "halal"],
];

const GOAL_WORDS: [RegExp, NutrientCode, number][] = [
  [/\bprotein\b/, "protein", 40],
  [/\bfib(?:er|re)\b/, "fiber", 15],
  [/\b(?:light|lighter|low[- ]?cal(?:orie)?s?)\b/, "calories", 450],
  [/\b(?:filling|hearty|hungry|big)\b/, "calories", 900],
  [/\b(?:low|less|lower|reduced)[- ]?(?:sodium|salt)\b/, "sodium", 300],
  [/\b(?:low|less|lower|no)[- ]?sugar\b|\bsugar[- ]free\b/, "sugar", 5],
  [/\b(?:low|less|lower)[- ]?fat\b|\blean\b/, "fat", 10],
  [/\b(?:low|less|lower)[- ]?carbs?\b|\bketo\b/, "carbs", 20],
];

const ALLERGEN_WORDS: Record<string, AllergenCode> = {
  peanut: "peanut", peanuts: "peanut",
  dairy: "milk", milk: "milk", cheese: "milk", lactose: "milk", cream: "milk", butter: "milk",
  egg: "egg", eggs: "egg",
  wheat: "wheat", gluten: "wheat",
  soy: "soy", soya: "soy", tofu: "soy",
  fish: "fish",
  shellfish: "shellfish", shrimp: "shellfish", prawn: "shellfish", prawns: "shellfish", crab: "shellfish", lobster: "shellfish",
  sesame: "sesame", mustard: "mustard", celery: "celery", lupin: "lupin",
  sulphites: "sulphites", sulfites: "sulphites",
};

const ALLERGEN_LABELS: Record<AllergenCode, string> = {
  peanut: "peanuts", milk: "dairy", egg: "eggs", wheat: "gluten", soy: "soy", fish: "fish",
  shellfish: "shellfish", sesame: "sesame", mustard: "mustard", celery: "celery", lupin: "lupin",
  sulphites: "sulphites",
};

const UNSUPPORTED: [RegExp, string][] = [
  [/\b(?:quick|quicker|fast|faster|ready in|\d+\s*(?:min|mins|minutes))\b/, "cooking time"],
  [/\b(?:chinese|malay|indian|peranakan|thai|vietnamese|japanese|korean|western|italian|mexican|middle eastern)\b/, "cuisine"],
  [/\b(?:spicy|spice|sweet|savou?ry|crispy|tangy)\b/, "flavour"],
];

const RESET = /\b(?:surprise me|start over|reset)\b/;

const PREFERRED_GOALS: Record<string, [NutrientCode, number]> = {
  Protein: ["protein", 40],
  Fibre: ["fiber", 15],
  "Lower sodium": ["sodium", 300],
  "Lower sugar": ["sugar", 5],
};

const unique = <T,>(items: T[]) => [...new Set(items)];

function negatedWords(text: string) {
  const words: string[] = [];
  for (const match of text.matchAll(/\b(?:no|without|avoid|skip|hold the|allergic to|free of)\b([^.!?;]*)/g)) {
    words.push(...match[1].split(/[^a-z]+/));
  }
  for (const match of text.matchAll(/\b([a-z]+)[- ]free\b/g)) {
    words.push(match[1]);
  }
  return words;
}

export function readPrompt(text: string): PromptReading {
  const lower = text.toLowerCase();
  const found: Constraints = { dietary: [], allergies: [], goals: {} };
  for (const [pattern, code] of DIETARY_WORDS) {
    if (pattern.test(lower)) found.dietary.push(code);
  }
  for (const [pattern, code, value] of GOAL_WORDS) {
    if (pattern.test(lower)) found.goals[code] = value;
  }
  found.allergies = unique(negatedWords(lower).flatMap((word) => ALLERGEN_WORDS[word] ?? []));
  const understood = found.dietary.length > 0 || found.allergies.length > 0 || Object.keys(found.goals).length > 0;
  return {
    found,
    unsupported: UNSUPPORTED.filter(([pattern]) => pattern.test(lower)).map(([, label]) => label),
    reset: RESET.test(lower),
    understood,
  };
}

export function mergeConstraints(base: Constraints, extra: Constraints): Constraints {
  return {
    dietary: unique([...base.dietary, ...extra.dietary]),
    allergies: unique([...base.allergies, ...extra.allergies]),
    goals: { ...base.goals, ...extra.goals },
  };
}

export function fromPreferences(
  stored: { special_diet: string | null; preferred_nutrient: string | null } | null,
): Constraints {
  const diet = stored?.special_diet;
  const preferred = stored?.preferred_nutrient ? PREFERRED_GOALS[stored.preferred_nutrient] : undefined;
  return {
    dietary: diet === "halal" || diet === "vegetarian" ? [diet] : [],
    allergies: [],
    goals: preferred ? { [preferred[0]]: preferred[1] } : {},
  };
}

export function ideaRequest(constraints: Constraints, random: () => number = Math.random): PlanRequest {
  const goals = Object.keys(constraints.goals).length
    ? constraints.goals
    : { calories: 500 + Math.round(random() * 600) };
  return {
    horizon_days: 3,
    meals_per_day: 1,
    servings: 1,
    ...(constraints.dietary.length ? { dietary: constraints.dietary.map((code) => ({ code })) } : {}),
    ...(constraints.allergies.length ? { allergies: constraints.allergies.map((code) => ({ code })) } : {}),
    nutrients: (Object.entries(goals) as [NutrientCode, number][]).map(([code, value]) => ({
      code,
      unit: UNITS[code],
      goal: { value },
    })),
  };
}

export function uniqueIdeas(plan: PlanResponse): PlanMeal[] {
  const seen = new Set<string>();
  return plan.days.flatMap((day) => day.meals).filter((meal) => {
    if (seen.has(meal.recipe_id)) return false;
    seen.add(meal.recipe_id);
    return true;
  });
}

function goalLabel(code: NutrientCode, value: number) {
  switch (code) {
    case "calories": return value <= 600 ? "lighter" : "filling";
    case "protein": return "high protein";
    case "fiber": return "high fibre";
    case "sodium": return "lower sodium";
    case "sugar": return "lower sugar";
    case "fat": return "lower fat";
    case "carbs": return "lower carb";
    default: return code.replaceAll("_", " ");
  }
}

export function describeConstraints(constraints: Constraints) {
  return [
    ...constraints.dietary,
    ...(Object.entries(constraints.goals) as [NutrientCode, number][]).map(([code, value]) => goalLabel(code, value)),
    ...constraints.allergies.map((code) => `no ${ALLERGEN_LABELS[code]}`),
  ];
}

const joinList = (items: string[]) =>
  items.length <= 1 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;

export function replyFor(ideas: PlanMeal[], constraints: Constraints, reading: PromptReading) {
  const labels = describeConstraints(constraints);
  const parts = [
    ideas.length === 0
      ? "I couldn't find anything that fits that."
      : `${ideas.length === 1 ? "Here's 1 idea" : `Here are ${ideas.length} ideas`}${labels.length ? ` for ${joinList(labels)}` : ""}.`,
  ];
  if (reading.unsupported.length) {
    parts.push(`I can't filter by ${joinList(reading.unsupported)} yet.`);
  } else if (!reading.understood && !reading.reset) {
    parts.push("Try words like “vegetarian”, “no dairy” or “more protein” to steer me.");
  }
  const note = constraints.dietary.length || constraints.allergies.length
    ? "The planner doesn't apply diet or allergy filters yet, so check the ingredients."
    : undefined;
  return { text: parts.join(" "), note };
}
