import pluralize from "pluralize";

// Remove filler and preparation words, but retain food-defining descriptors
// such as dried, cooked, raw, red, white, unsalted, and gluten-free.
const SKIP_WORDS = new Set([
  "a", "an", "the", "some", "of", "for", "please",
  "fresh", "freshly", "finely", "roughly", "coarsely", "thinly",
  "chopped", "diced", "sliced", "minced", "peeled", "grated",
  "rinsed", "drained", "halved", "quartered", "large", "medium", "small",
]);

// Food names that English inflection rules can otherwise misinterpret.
const KEEP_WORDS = new Set(["asparagus", "couscous", "hummus", "molasses", "watercress"]);

export function normalizeIngredientName(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter((word) => word && !SKIP_WORDS.has(word))
    .map((word) => KEEP_WORDS.has(word) ? word : pluralize.singular(word))
    .join(" ");
}
