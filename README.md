# Remy: An Intelligent Knowledge Base for Meal Planning Application


## EXECUTIVE SUMMARY / PAPER ABSTRACT
Remy is a weekly meal-planning recommendation application that helps users choose recipes while considering nutrition, ingredient availability, approximate grocery cost, and dietary evidence. The project treats meal planning as a data-integration and reasoning problem. A recipe is represented through its ingredient requirements; each requirement is linked to a normalized food concept; candidate nutrition profiles are used to estimate nutrients and FairPrice evidence is attached to the product or offer that can satisfy the requirement. A generic food profile, a branded product, and a dated retail offer therefore remain separate records.

A typical user request may combine a carbohydrate range, an excluded allergen, a halal or vegetarian preference, and a daily food budget. Remy models these as explicit constraints. Its reasoning flow is to identify the ingredient occurrences required by a recipe, find compatible food candidates, verify nutrition and dietary evidence, calculate the portion-level contribution, and estimate cost when package and price information are sufficient.

---

## CREDITS / PROJECT CONTRIBUTION

| Official Full Name  | Student ID (MTech Applicable)  | Work Items (Who Did What) | Email (Optional)      |
|:--------------------|:---------------:| :-----|:----------------------|
| Le Chi Thanh        | A0352811L | Data preparation, modelling and system architecturing | thanhlc@u.nus.edu     |
| Vuong Quang Viet Tung  | A0357416Y |Data preparation, front-end application | viettungvuong@u.nus.edu   |
| Tran Dinh Gia Khanh | A0359890J | Workflow for the application (LangGraph), front end application | khanh.dg.tran@u.nus.edu |
---

## VIDEO OF SYSTEM MODELLING & USE CASE DEMO
TBU
---

## USER GUIDE

### Run Remy on your computer

One command starts the whole app in Docker: the database, the sign-in service,
the Remy API and the web app.

**You need**

- [Docker Desktop](https://www.docker.com/products/docker-desktop/), open and running.
  On Windows, run the commands below in WSL.
- Git.
- The connection details for the Neo4j recipe database (ask the team).

**1. Get the code**

```bash
git clone https://github.com/2na3k/Workshop-Project-Submission-2026-10-10-AIS.git
cd Workshop-Project-Submission-2026-10-10-AIS/SystemCode
```

**2. Create the settings file**

```bash
cp .env.example .env.nonprod
uv run --package remy-api python scripts/init_langfuse.py --path .env.nonprod
```

Then fill in `NEO4J_*` (and `NEO4J_DOCKER_URI=bolt://host.docker.internal:7687` for a
local Neo4j) and `REMY_JWT_SECRET` (`openssl rand -base64 48`). The
`init_langfuse.py` step generates the Langfuse and database secrets. The file is
git-ignored. `.env.prod` has the same keys for production. Full list:
[SystemCode/docs/docker_compose.md](SystemCode/docs/docker_compose.md).

**3. Build and start with Docker Compose**

Run these from `SystemCode/`:

```bash
docker compose --env-file .env.nonprod build
docker compose --env-file .env.nonprod up -d --wait   # start everything and wait until healthy
```

`--wait` returns once every service passes its health check. Check them with
`docker compose --env-file .env.nonprod ps`; each should show `(healthy)`.

Then open the web app:

| What                 | Address                    |
|:---------------------|:---------------------------|
| Web app              | http://localhost:3100      |
| Remy API docs        | http://localhost:8000/docs |
| Sign-in service docs | http://localhost:8010/docs |
| Langfuse dashboard   | http://localhost:3031      |

```bash
docker compose --env-file .env.nonprod logs -f   # follow the logs of all services
docker compose --env-file .env.nonprod down      # stop Remy; accounts are kept for the next start
```

Shortcut: `./remy/start-all.sh` does the build and start, opens the browser when
everything is ready, and shows the logs. Press Ctrl+C to stop it.

The demo account is `demo` / `remy-demo-account`, or click **Try the demo**.

**Accounts:** the app has no admin account and no roles. The only account it seeds is
the public `demo` account (`remy/backend/db.sql`); its password is in the frontend
bundle, so treat it as public. Anyone else signs up for their own account. The Langfuse
dashboard has a separate admin login from `.env.nonprod`.

**4. Use it**

Create an account, set your diet and goals under **Your preferences**, then build a
weekly plan on the **Meal plan** page. The **Discover** page suggests meals from a
short request such as "something filling, no dairy" and calculates the cost and
nutrition of an ingredient.

**If something goes wrong**

- *A port is already in use*: close whatever uses it, or pick other ports, for example
  `FRONTEND_PORT=3101 docker compose --env-file .env.nonprod up -d --wait`.
- *Plans or the calculator show an error*: check the `NEO4J_*` values in `.env.nonprod`,
  then read `docker compose --env-file .env.nonprod logs api`. If plans say
  "No recipes with complete nutrition data", run the fulfillment rebuild in the
  guide above.
- *Docker is not running*: open Docker Desktop and run the command again.

More detail, including everyday commands, settings and troubleshooting:
[SystemCode/docs/docker_compose.md](SystemCode/docs/docker_compose.md).

---
## PROJECT REPORT / PAPER

`Refer to project report at Github Folder: ProjectReport`
TBU

---
## MISCELLANEOUS

`Refer to Github Folder: Miscellaneous`
TBU

---
