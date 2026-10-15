/** Shared by the cold start wizard and the in-app preferences editor, so the
 *  two can never drift apart. Diet ids match the CHECK constraint on
 *  preference.special_diet in api/sql/02_schema.sql. */

export const DIETS = [
  { id: "halal", label: "Halal", hint: "Halal-certified ingredients only" },
  { id: "vegetarian", label: "Vegetarian", hint: "No meat or seafood" },
  { id: "meat", label: "Meat", hint: "Anything goes" },
] as const;

export const CUISINES = [
  "Chinese", "Malay", "Indian", "Peranakan", "Thai", "Vietnamese",
  "Japanese", "Korean", "Western", "Italian", "Mexican", "Middle Eastern",
] as const;

export const NUTRIENTS = ["Protein", "Fibre", "Lower sodium", "Lower sugar"] as const;

export type Diet = (typeof DIETS)[number]["id"];

export type Preferences = {
  diet: Diet | null;
  cuisines: string[];
  nutrient: string | null;
};

export const EMPTY_PREFERENCES: Preferences = {
  diet: null,
  cuisines: [],
  nutrient: null,
};
