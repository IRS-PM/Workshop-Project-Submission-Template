import os
from decimal import Decimal

from neo4j import GraphDatabase


OWNER = "remy_recipe_graph"

NODES = (
    ("Recipe", "node_recipe", "recipe_id"),
    ("FoodConcept", "node_food_concept", "canonical_key"),
    ("Food", "node_food", "food_key"),
    ("Component", "node_component", "component_id"),
)
RETIRED_LABELS = ("Product", "Offer", "Allergen", "Diet")

NODE_STATEMENTS = {
    label: (
        "UNWIND $rows AS row\n"
        + "MERGE (n:" + label + " {" + key + ": row." + key + "})\n"
        + "SET n += row, n.projection_owner = '" + OWNER + "'"
    )
    for label, _, key in NODES
}

EDGE_LOADS = (
    ("REQUIRES", "edge_requires", """
UNWIND $rows AS row
MATCH (a:Recipe {recipe_id: row.recipe_id})
MATCH (b:FoodConcept {canonical_key: row.normalized_name})
MERGE (a)-[e:REQUIRES {occurrence_id: row.occurrence_id}]->(b)
SET e += row, e.projection_owner = $owner
"""),
    ("FOOD_FULFILLS", "edge_fulfills", """
UNWIND $rows AS row
MATCH (a:Food {food_key: row.food_key})
MATCH (b:FoodConcept {canonical_key: row.canonical_key})
MERGE (a)-[e:FULFILLS {candidate_key: row.candidate_key}]->(b)
SET e += row, e.projection_owner = $owner
"""),
    ("HAS_COMPONENT", "edge_has_component", """
UNWIND $rows AS row
MATCH (a:Food {food_key: row.food_key})
MATCH (b:Component {component_id: row.component_id})
MERGE (a)-[e:HAS_COMPONENT {id: row.id}]->(b)
SET e += row, e.projection_owner = $owner
"""),
)


def _rows(relation, batch_size):
    while rows := relation.fetchmany(batch_size):
        yield [
            {
                column: float(value) if isinstance(value, Decimal) else value
                for column, value in zip(relation.columns, row, strict=True)
            }
            for row in rows
        ]


def model(dbt, session):
    dbt.config(materialized="table", tags=["serving"])
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise ValueError("NEO4J_PASSWORD must be set")
    batch_size = int(os.getenv("NEO4J_BATCH_SIZE") or "5000")
    if batch_size <= 0:
        raise ValueError("NEO4J_BATCH_SIZE must be positive")

    manifest_rows = []
    for batch in _rows(dbt.ref("graph_quality_manifest"), batch_size):
        manifest_rows.extend(batch)
    if any(not row["within_allocation"] for row in manifest_rows):
        failed = ", ".join(row["entity"] for row in manifest_rows if not row["within_allocation"])
        raise ValueError(f"graph_quality_manifest allocation failed: {failed}")
    manifest = {row["entity"]: row["row_count"] for row in manifest_rows}
    projected_nodes = manifest.get("TOTAL_NODE")
    projected_relationships = manifest.get("TOTAL_RELATIONSHIP")
    if projected_nodes is None or projected_relationships is None:
        raise ValueError("graph_quality_manifest totals are required")

    replace = os.getenv("NEO4J_REPLACE", "").lower() in {"1", "true", "yes"}
    if not replace:
        raise ValueError("NEO4J_REPLACE=true is required so stale projection-owned facts are withdrawn")
    uri = os.getenv("NEO4J_URI") or "bolt://localhost:7687"
    user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
    driver = GraphDatabase.driver(uri, auth=(user, password))
    neo4j = driver.session(database=os.getenv("NEO4J_DATABASE") or "neo4j")

    def run(statement, **parameters):
        return neo4j.run(statement, **parameters).single()

    occupancy = run("MATCH (n) WITH count(n) AS nodes OPTIONAL MATCH ()-[r]->() RETURN nodes, count(r) AS relationships")
    if occupancy["nodes"] > 180000 or occupancy["relationships"] > 360000:
        neo4j.close()
        driver.close()
        raise ValueError("Neo4j current occupancy already exceeds the operational gate")

    for label, _, key in NODES:
        run(f"CREATE CONSTRAINT remy_{label.lower()}_{key} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")

    loads = (
        ("Recipe", dbt.ref("node_recipe"), NODE_STATEMENTS["Recipe"]),
        ("FoodConcept", dbt.ref("node_food_concept"), NODE_STATEMENTS["FoodConcept"]),
        ("Food", dbt.ref("node_food"), NODE_STATEMENTS["Food"]),
        ("Component", dbt.ref("node_component"), NODE_STATEMENTS["Component"]),
        ("REQUIRES", dbt.ref("edge_requires"), EDGE_LOADS[0][2]),
        ("FULFILLS", dbt.ref("edge_fulfills"), EDGE_LOADS[1][2]),
        ("HAS_COMPONENT", dbt.ref("edge_has_component"), EDGE_LOADS[2][2]),
    )
    transaction = neo4j.begin_transaction()

    def tx_run(statement, **parameters):
        return transaction.run(statement, **parameters).single()

    counts = []
    try:
        while True:
            result = tx_run(
                "MATCH ()-[r]->() WHERE r.projection_owner = $owner WITH r LIMIT $limit DELETE r RETURN count(*) AS deleted",
                owner=OWNER, limit=batch_size,
            )
            if result["deleted"] < batch_size:
                break
        for label in tuple(label for label, _, _ in NODES) + RETIRED_LABELS:
            while True:
                result = tx_run(
                    f"MATCH (n:{label}) WHERE n.projection_owner = $owner AND NOT (n)--() WITH n LIMIT $limit DELETE n RETURN count(*) AS deleted",
                    owner=OWNER, limit=batch_size,
                )
                if result["deleted"] < batch_size:
                    break
        remaining = tx_run("MATCH (n) WITH count(n) AS nodes OPTIONAL MATCH ()-[r]->() RETURN nodes, count(r) AS relationships")
        final_nodes = remaining["nodes"] + projected_nodes
        final_relationships = remaining["relationships"] + projected_relationships

        if final_nodes > 180000 or final_relationships > 360000:
            raise ValueError(f"Neo4j operational capacity gate failed: nodes={final_nodes}, relationships={final_relationships}")

        for entity, relation, statement in loads:
            loaded = 0
            for payload in _rows(relation, batch_size):
                tx_run(statement, rows=payload, owner=OWNER)
                loaded += len(payload)
            counts.append((entity, loaded))
        transaction.commit()
    except Exception:
        try:
            transaction.rollback()
        except Exception:
            pass
        raise
    finally:
        neo4j.close()
        driver.close()
    return session.sql(" UNION ALL ".join(
        f"SELECT '{entity}' AS entity, {loaded} AS loaded_rows" for entity, loaded in counts
    ))
