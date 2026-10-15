import importlib.util
import os
from pathlib import Path
from unittest.mock import patch


path = Path(__file__).parents[1] / "models/serving/recipe_graph_to_neo4j.py"
spec = importlib.util.spec_from_file_location("recipe_graph_to_neo4j", path)
serving = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(serving)


class Result:
    def __init__(self, value):
        self.value = value

    def single(self):
        return self.value


class Transaction:
    def __init__(self, neo4j, fail_on_load=False):
        self.neo4j = neo4j
        self.fail_on_load = fail_on_load
        self.committed = False
        self.rolled_back = False

    def run(self, statement, **parameters):
        requests.append((statement, parameters))
        if self.fail_on_load and "UNWIND $rows" in statement:
            raise RuntimeError("injected load failure")
        return Result(self.neo4j.result_for(statement))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class Neo4jSession:
    def __init__(self, nodes=10, relationships=20, fail_on_load=False):
        self.nodes = nodes
        self.relationships = relationships
        self.transaction = Transaction(self, fail_on_load)

    def result_for(self, statement):
        if "WITH count(n) AS nodes" in statement:
            return {"nodes": self.nodes, "relationships": self.relationships}
        if "RETURN count(n) AS nodes" in statement:
            return {"nodes": 5}
        if "RETURN count(r) AS relationships" in statement:
            return {"relationships": 5}
        if "deleted" in statement:
            return {"deleted": 0}
        return {}

    def run(self, statement, **parameters):
        requests.append((statement, parameters))
        return Result(self.result_for(statement))

    def begin_transaction(self):
        return self.transaction

    def close(self):
        pass


class Driver:
    def __init__(self, neo4j):
        self.neo4j = neo4j

    def session(self, database):
        assert database == "database"
        return self.neo4j

    def close(self):
        pass


class Relation:
    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = iter(rows)

    def fetchmany(self, size):
        return [row for _, row in zip(range(size), self.rows)]


class Dbt:
    def config(self, **_):
        pass

    def ref(self, name):
        if name == "graph_quality_manifest":
            return Relation(
                ["entity", "row_count", "allocation", "within_allocation"],
                [("TOTAL_NODE", 8, 84200, True), ("TOTAL_RELATIONSHIP", 8, 208200, True)],
            )
        return Relation(["id"], [(1,)])


class Session:
    def sql(self, query):
        return query


def environment(replace=False):
    values = {
        "NEO4J_URI": "neo4j+s://example.databases.neo4j.io",
        "NEO4J_USERNAME": "user",
        "NEO4J_PASSWORD": "secret",
        "NEO4J_DATABASE": "database",
    }
    if replace:
        values["NEO4J_REPLACE"] = "true"
    return values


requests = []
with patch.dict(os.environ, environment(), clear=True):
    try:
        serving.model(Dbt(), Session())
    except ValueError as error:
        assert "NEO4J_REPLACE=true is required" in str(error)
    else:
        raise AssertionError("append-only synchronization was accepted")
assert not requests

requests.clear()
replacement = Neo4jSession(nodes=179990, relationships=359990)
with (
    patch.dict(os.environ, environment(replace=True), clear=True),
    patch.object(serving.GraphDatabase, "driver", return_value=Driver(replacement)) as connect,
):
    result = serving.model(Dbt(), Session())
connect.assert_called_once_with("neo4j+s://example.databases.neo4j.io", auth=("user", "secret"))
assert replacement.transaction.committed and not replacement.transaction.rolled_back
assert any("DELETE r" in statement for statement, _ in requests)
statements = "\n".join(statement for statement, _ in requests)
assert "projection_owner" in statements
assert "Product" in statements and "Offer" in statements and "Allergen" in statements and "Diet" in statements
assert "candidate_key" in statements
assert "FULFILLS" in result and "HAS_COMPONENT" in result
assert "PRODUCT_FULFILLS" not in result and "DIET_STATUS" not in result

requests.clear()
failing = Neo4jSession(fail_on_load=True)
with (
    patch.dict(os.environ, environment(replace=True), clear=True),
    patch.object(serving.GraphDatabase, "driver", return_value=Driver(failing)),
):
    try:
        serving.model(Dbt(), Session())
    except RuntimeError as error:
        assert "injected load failure" in str(error)
    else:
        raise AssertionError("injected load failure was not raised")
assert failing.transaction.rolled_back and not failing.transaction.committed

requests.clear()
over_capacity = Neo4jSession(nodes=180000)
with (
    patch.dict(os.environ, environment(replace=True), clear=True),
    patch.object(serving.GraphDatabase, "driver", return_value=Driver(over_capacity)),
):
    try:
        serving.model(Dbt(), Session())
    except ValueError as error:
        assert "capacity gate failed" in str(error)
    else:
        raise AssertionError("capacity gate accepted an over-cap load")
assert over_capacity.transaction.rolled_back


class BadManifestDbt(Dbt):
    def ref(self, name):
        if name == "graph_quality_manifest":
            return Relation(
                ["entity", "row_count", "allocation", "within_allocation"],
                [("Food", 32001, 32000, False), ("TOTAL_NODE", 32001, 84200, True),
                 ("TOTAL_RELATIONSHIP", 0, 208200, True)],
            )
        return super().ref(name)


with patch.dict(os.environ, environment(), clear=True):
    try:
        serving.model(BadManifestDbt(), Session())
    except ValueError as error:
        assert "allocation failed: Food" in str(error)
    else:
        raise AssertionError("individual manifest allocation failure was accepted")
