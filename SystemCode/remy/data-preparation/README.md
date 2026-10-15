# Data preparation

This dbt project transforms recipe, FoodData Central, and FairPrice data in DuckDB/DuckLake, then loads the curated recipe graph into Neo4j.

## Setup

From `SystemCode`:

1. Download the seed data from [Google Drive](https://drive.google.com/drive/folders/1Gvgsyn0SwnXeCXB457-B1KTeu11VjmrI?usp=sharing).
2. Place it under `remy/data-preparation/seeds` with these files:

   ```text
   13k-recipe/13k-recipes.csv
   central_food/branded_food.csv
   central_food/food.csv
   central_food/food_component.csv
   central_food/food_nutrient/data.parquet
   fairprice/price_mapped_nutrients.csv
   ```

3. Install dependencies and build the models:

   ```bash
   make install
   make dbt
   ```

The default target is `nonprod`; use `DBT_TARGET=prod make dbt` for production.

## Common commands

```bash
make dbt-all       # Build dbt models and load Neo4j
make serve-neo4j   # Load already-built marts into Neo4j
```

Set `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE` in `SystemCode/.env.nonprod` (or `.env.prod`) before loading Neo4j.

Run a recipe cost and nutrition estimate without Neo4j:

```bash
uv run --package remy-data-preparation \
  python remy/data-preparation/scripts/recipe_estimate.py 882 \
  --assumed-servings 2 --requested-portions 1 --halal-mode off
```
