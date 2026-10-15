"""Rebuild :BEST_FULFILLMENT edges after data preparation."""
import logging
from datetime import datetime, timezone

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


DELETE_STMT = """
MATCH ()-[b:BEST_FULFILLMENT]->()
CALL (b) { DELETE b } IN TRANSACTIONS OF 10000 ROWS
"""

CREATE_STMT = """
MATCH (fc:FoodConcept)<-[ful:FULFILLS]-(f:Food)
WHERE ful.approval_status = 'accepted'

WITH fc, ful, f
ORDER BY
  coalesce(ful.nutrition_rank, 2147483647),
  coalesce(ful.selection_priority, 2147483647),
  coalesce(f.food_key, '~')

WITH fc, head(collect({ful: ful, f: f})) AS best
WITH fc, best.f AS selected_food, best.ful AS selected_ful

CREATE (fc)-[b:BEST_FULFILLMENT]->(selected_food)
SET b.selected_at = datetime(),
    b.snapshot_id = $snapshot_id,
    b.food_key = selected_food.food_key,
    b.nutrition_rank = selected_ful.nutrition_rank,
    b.selection_priority = selected_ful.selection_priority,
    b.vegetarian_status = selected_ful.vegetarian_status,
    b.vegetarian_evidence_kind = selected_ful.vegetarian_evidence_kind,
    b.vegetarian_concerns = selected_ful.vegetarian_concerns,
    b.may_non_vegetarian = selected_ful.may_non_vegetarian,
    b.halal_status = selected_ful.halal_status,
    b.halal_evidence_kind = selected_ful.halal_evidence_kind,
    b.halal_freshness_status = selected_ful.halal_freshness_status,
    b.allergen_evidence_kinds = selected_ful.allergen_evidence_kinds,
    b.potential_allergens = selected_ful.potential_allergens,
    b.may_allergic = selected_ful.may_allergic,
    b.allergen_screening_status = selected_ful.allergen_screening_status
RETURN count(b) AS BestFulfillmentsCreated
"""


def rebuild_best_fulfillment(driver, snapshot_id: str | None = None) -> int:
    if snapshot_id is None:
        snapshot_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with driver.session() as session:
        logger.info("Deleting old BEST_FULFILLMENT edges...")
        session.run(DELETE_STMT).consume()

        logger.info("Creating new BEST_FULFILLMENT edges...")
        record = session.run(CREATE_STMT, snapshot_id=snapshot_id).single()
        total_created = record["BestFulfillmentsCreated"] if record else 0

    logger.info(
        "Rebuilt %d BEST_FULFILLMENT edges (snapshot_id=%s)",
        total_created, snapshot_id,
    )
    return total_created


if __name__ == "__main__":
    from pathlib import Path
    from dotenv import load_dotenv
    import os

    SHARED_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv(SHARED_ENV_PATH)

    logging.basicConfig(level=logging.INFO)

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        count = rebuild_best_fulfillment(driver)
        print(f"✅ Rebuilt {count} BEST_FULFILLMENT edges")
    finally:
        driver.close()
