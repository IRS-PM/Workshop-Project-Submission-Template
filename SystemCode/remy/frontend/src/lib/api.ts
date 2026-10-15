/** Client for the FastAPI backend in ../../backend.
 *
 *  There is no token handling here. The session lives in an HttpOnly cookie
 *  that this code cannot read or write - the browser attaches it automatically
 *  because every request below sets `credentials: "include"`. That is the point
 *  of the arrangement: an XSS bug cannot exfiltrate a token it cannot see. */

import type { PlanMeal } from "@/lib/plan-api";

// The session cookie is scoped to the host that answered the sign-in. Use the
// host the page itself was opened on (localhost or 127.0.0.1), or the browser
// treats the API as another site and drops the cookie.
const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_URL =
  typeof window === "undefined"
    ? configuredApiUrl
    : configuredApiUrl.replace(/\/\/[^/:]+/, `//${window.location.hostname}`);

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type Credentials = { username: string; password: string };

export type PreferencesPayload = {
  special_diet: string | null;
  cuisines: string[];
  preferred_nutrient: string | null;
};

type SessionResponse = { username: string; expires_at: number };

/** FastAPI returns `detail` as a string for HTTPException and as a list of
 *  `{loc, msg}` for request validation errors. Flatten both to one line. */
function messageFrom(payload: unknown, status: number): string {
  const detail = (payload as { detail?: unknown } | null)?.detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    if (typeof first?.msg === "string") return first.msg;
  }

  return `Something went wrong (${status}).`;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      // Sends and accepts the session cookie across the origin boundary. The
      // backend must name this exact origin in CORS and allow credentials -
      // a wildcard origin is rejected by the browser when this is set.
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // fetch only rejects when the request never completed: backend down, wrong
    // port, CORS preflight refused. Status 0 marks "no response at all".
    throw new ApiError(
      `Cannot reach the server. Is the backend running on ${API_URL}?`,
      0,
    );
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(messageFrom(payload, response.status), response.status);
  }

  return payload as T;
}

export const signUp = (credentials: Credentials) =>
  request<SessionResponse>("POST", "/auth/signup", credentials);

export const signIn = (credentials: Credentials) =>
  request<SessionResponse>("POST", "/auth/signin", credentials);

/** The demo account seeded by backend/db.sql. The password is in the bundle
 *  on purpose - it guards nothing. */
export const signInDemo = () =>
  signIn({ username: "demo", password: "remy-demo-account" });

export const checkUsername = (username: string) =>
  request<{ username: string; available: boolean; answered_by_filter: boolean }>(
    "POST",
    "/auth/available",
    { username },
  );

/** Clearing the cookie is a server call - script cannot delete an HttpOnly one. */
export const logOut = () => request<void>("POST", "/auth/logout");

/** Renews the cookie. The backend re-sets it even when the same token comes
 *  back, so the expiry slides forward on every app open. */
export const refreshSession = () =>
  request<{ expires_at: number; refreshed: boolean }>("POST", "/auth/refresh");

/** Who the cookie belongs to. This is the only proof of a session the frontend
 *  has, since it cannot inspect the token itself. */
export const fetchAccount = () => request<{ username: string }>("GET", "/me");

/** First write, from the cold start. Rides on the cookie /auth/signup just set. */
export const createPreferences = (preferences: PreferencesPayload) =>
  request<PreferencesPayload & { username: string }>(
    "POST",
    "/preferences",
    preferences,
  );

export const savePreferences = (preferences: PreferencesPayload) =>
  request<PreferencesPayload & { username: string }>(
    "PUT",
    "/preferences",
    preferences,
  );

/** Resolves to null when nothing has been saved yet (the backend 404s). */
export async function loadPreferences(): Promise<PreferencesPayload | null> {
  try {
    return await request<PreferencesPayload>("GET", "/preferences");
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) return null;
    throw caught;
  }
}

/** Meals kept from the home page ideas, newest first. */
export const listSavedMeals = () => request<PlanMeal[]>("GET", "/saved");

/** Resolves to the full saved list after the new ones are added. */
export const saveMeals = (meals: PlanMeal[]) =>
  request<PlanMeal[]>("POST", "/saved", { meals });

export const removeSavedMeal = (recipeId: string) =>
  request<void>("DELETE", `/saved/${encodeURIComponent(recipeId)}`);

/** One History row: the meal, whether it was liked, and when (ISO 8601). */
export type MealRating = { meal: PlanMeal; like: boolean; rated_at: string };

/** Every meal the user rated, newest first. */
export const listRatings = () => request<MealRating[]>("GET", "/ratings");

/** Rating a meal again changes its like and moves it to the top of History. */
export const rateMeal = (meal: PlanMeal, like: boolean) =>
  request<MealRating>("PUT", `/ratings/${encodeURIComponent(meal.recipe_id)}`, { like, meal });
