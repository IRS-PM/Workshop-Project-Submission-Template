This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Integrated Docker + real browser E2E

From `SystemCode/`, with the settings in `.env.nonprod`:

```sh
docker compose --env-file .env.nonprod up -d --build --wait
```

This repo's webapp is **http://localhost:3100**. The auth/preferences backend is on
8010, the Remy API on 8000, and the Langfuse dashboard on `LANGFUSE_PORT` (default
3031). Sign up to create a local account, or use the demo account `demo` /
`remy-demo-account`.

From `SystemCode/remy/frontend/`:

```sh
npm ci
npx playwright install chromium
npm run test:e2e
```

The real Chromium test signs up a random test account, saves preferences, logs out
and back in, generates a streamed plan through Next.js -> API -> production Neo4j,
checks all six Langfuse spans and the blind-grading snapshot, and verifies the
passwordless dashboard session. No mocked food API or fabricated human grades.
It creates a local test account/snapshot/trace; artifacts are in
`SystemCode/target/e2e/{meal-plan.png,result.json}` (gitignored).

Next.js was patched to 16.4.0 for the inherited critical advisory. Production
`npm audit --omit=dev` reports zero vulnerabilities; five inherited lint-tool
advisories remain (fixing them via npm's suggested downgrade would break Next 16).
Allergen/dietary requests run through per-recipe screening of known conflicts.
Unknown evidence is not a blanket rejection: results are marked `unverified`, with
explicit warnings in plan and chat UIs. They are not certified allergy-safe or
diet-compliant. E2E also exercises Halal, Vegetarian, and Peanuts selections.

## Ingredient calculator

The home page has a separate **Check an ingredient** search bar. Enter one
ingredient name and choose its quantity, unit, and number of servings (defaults:
100 g, 1 serving). The name is lowercased, preparation/filler words are removed,
and plural words are singularized before submission. The normalized name is
shown beneath the input. Quantity and unit come from their controls, not the name.

## Meal plan

The **Meal plan** page (`/plan`) calls `POST /api/v1/plan`. It prefills diet and
one nutrient target from the saved preferences, then lets the user set days
(1–14), meals a day (1–6), servings, allergies, and per-day nutrient targets.

## Connecting to the backends

| Service | Endpoints | How the frontend reaches it |
| ------- | --------- | --------------------------- |
| Remy Backend (`remy/backend`) | `/auth/*`, `/me`, `/preferences` | Directly from the browser at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), with the session cookie |
| Remy API (`remy/api`) | `/api/v1/calculate/*`, `/api/v1/plan` | Through a Next.js rewrite of `/api/v1/*` to `REMY_API_URL` (default `http://localhost:8081`) |

The Remy API has no CORS middleware, so the proxy is required. Start it from
`SystemCode` on the port `REMY_API_URL` points to:

```bash
uv run --package remy-api uvicorn api.main:app --reload --port 8081
```

To use another port, set `REMY_API_URL` in `.env.local` and restart the frontend.
The calculator and planner require the API's populated Neo4j database.

Run `npm test` for normalization, calculator, and planner request/error tests
(Node 22.18+ for native TypeScript support), and `npm run lint` for lint checks.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
