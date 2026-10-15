"""Run: uv run --package remy-api python -m unittest discover -s remy/api/tests -p test_monitoring.py"""

import json
import math
import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.core import monitoring
from api.features.plan.evaluation import evaluation_db
from api.features.plan.metrics import ranking_metrics
from api.features.plan.models import Ingredient, Recipe
from api.features.plan.dependencies import get_plan_service
from api.features.plan.schemas import PlanRequest
from api.features.plan.service import PlanService


class RecordingClient:
    def __init__(self):
        self.spans, self.scores = [], []

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        span = RecordingSpan(kwargs)
        self.spans.append(span)
        yield span

    def create_score(self, **kwargs):
        self.scores.append(kwargs)


class RecordingSpan:
    trace_id = "1234567890abcdef1234567890abcdef"

    def __init__(self, kwargs):
        self.kwargs, self.updates = kwargs, []

    def update(self, **kwargs):
        self.updates.append(kwargs)


class MetricsTests(unittest.TestCase):
    def test_metrics_and_edge_cases(self):
        ranked = ["a", "b", "c", "d"]
        perfect = ranking_metrics(ranked, dict(zip(ranked, [3, 2, 1, 0])))
        self.assertEqual(perfect, {"nDCG@3": 1.0, "Precision@3": 2 / 3, "pairwise_accuracy": 1.0})
        reversed_grades = ranking_metrics(ranked, dict(zip(ranked, [0, 1, 2, 3])))
        self.assertAlmostEqual(reversed_grades["nDCG@3"],
                               (1 / math.log2(3) + 3 / 2) / (7 + 3 / math.log2(3) + 1 / 2))
        self.assertEqual(reversed_grades["Precision@3"], 1 / 3)
        self.assertEqual(reversed_grades["pairwise_accuracy"], 0)
        self.assertEqual(ranking_metrics(["a", "b", "c"], {"a": 3, "b": 3, "c": 1})["pairwise_accuracy"], 1)
        zero = ranking_metrics(["a"], {"a": 0})
        self.assertEqual(zero, {"nDCG@3": 0.0, "Precision@3": 0.0, "pairwise_accuracy": None})
        self.assertEqual(ranking_metrics(["a"], {"a": 3})["Precision@3"], 1 / 3)
        for ranked, grades in [([], {}), (["a", "a"], {"a": 3}), (["a", "b"], {"a": 3}),
                               (["a"], {"a": 3, "b": 0}), (["a"], {"a": True}),
                               (["a"], {"a": 2.5}), (["a"], {"a": 4}), (["a"], {"a": -1})]:
            with self.assertRaises(ValueError):
                ranking_metrics(ranked, grades)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "LANGFUSE_TRACING_ENABLED": "false", "REMY_EVALUATION_TOKEN": "reviewer-test-token",
            "REMY_EVALUATION_DB": self.temp.name + "/evaluations.sqlite3",
        })
        self.env.start()
        monitoring.get_client.cache_clear()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.env.stop)
        self.addCleanup(monitoring.get_client.cache_clear)
        self.recording = RecordingClient()
        self.client_patch = patch("api.core.monitoring.get_client", return_value=self.recording)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.request = PlanRequest(horizon_days=1, meals_per_day=1,
                                   nutrients=[{"code": "calories", "unit": "kcal", "goal": {"value": 300}}])
        outer = self

        class Repository:
            def fetch_candidates(self):
                return [Recipe(recipe_id=key, title="Recipe " + key, ingredients=[Ingredient(
                    quantity=100, unit="g", text="food", nutrients={"calories": kcal},
                    nutrition_basis="per 100 g")]) for key, kcal in [("a", 200), ("b", 300), ("c", 100), ("d", 400)]]

        self.service = PlanService(Repository())
        from api.main import app

        previous_overrides = app.dependency_overrides.copy()
        self.addCleanup(setattr, app, "dependency_overrides", previous_overrides)
        app.dependency_overrides[get_plan_service] = lambda: outer.service
        self.http = TestClient(app)
        self.addCleanup(self.http.close)
        self.headers = {"Authorization": "Bearer reviewer-test-token"}

    def create(self):
        response = self.http.post("/api/v1/plan", json=self.request.model_dump())
        self.assertEqual(response.status_code, 200, response.text)
        for block in response.text.split("\n\n"):
            if block.startswith("event: plan\n"):
                return json.loads(block.split("data: ", 1)[1])
        self.fail("Stream ended without a plan event: " + response.text)

    def test_restricted_plans_run_and_unknown_evidence_is_not_claimed_safe(self):
        for restriction in ({"allergies": [{"code": "peanut"}]}, {"dietary": [{"code": "halal"}]}, {"dietary": [{"code": "vegetarian"}]}):
            response = self.http.post("/api/v1/plan", json={**self.request.model_dump(), **restriction})
            self.assertEqual(response.status_code, 200)
            block = next(b for b in response.text.split("\n\n") if b.startswith("event: plan\n"))
            plan = json.loads(block.split("data: ", 1)[1])
            self.assertEqual(plan["status"], "partial")
            self.assertIn("unverified", plan["validation_summary"].values())
            self.assertNotIn("passed", plan["validation_summary"].values())
            self.assertEqual(len(self.recording.spans[-6:]), 6)

    def test_known_conflicts_are_filtered_not_every_restricted_request(self):
        from api.features.plan.filtering import filter_candidates
        for restriction, ingredient in (
            ({"allergies": [{"code": "peanut"}]}, {"potential_allergens": ["peanut"]}),
            ({"allergies": [{"code": "milk"}]}, {"text": "milk"}),
            ({"dietary": [{"code": "halal"}]}, {"halal_status": "non_compliant"}),
            ({"dietary": [{"code": "vegetarian"}]}, {"vegetarian_status": "potential_not_vegetarian"}),
            ({"dietary": [{"code": "vegetarian"}]}, {"text": "chicken"}),
        ):
            candidates = self.service.repository.fetch_candidates()
            for key, value in ingredient.items():
                setattr(candidates[0].ingredients[0], key, value)
            request = PlanRequest.model_validate({**self.request.model_dump(), **restriction})
            self.assertEqual([r.recipe_id for r in filter_candidates(candidates, request)], ["b", "c", "d"])

    def test_disabled_and_snapshot_failure_do_not_change_plan(self):
        with patch("api.core.monitoring.get_client", return_value=None), patch.dict(os.environ, {"REMY_EVALUATION_TOKEN": ""}):
            result = self.create()
            self.assertIsNone(result["trace_id"])
            self.assertIsNone(result["evaluation_id"])
            self.assertEqual(result["status"], "complete")
            self.assertEqual(self.http.get("/api/v1/evaluations/00000000-0000-0000-0000-000000000000").status_code, 503)
        with patch("api.features.plan.service.save_evaluation", side_effect=OSError("disk unavailable")):
            result = self.create()
            self.assertIsNone(result["evaluation_id"])
            self.assertEqual(result["status"], "complete")

    def test_business_failure_is_not_swallowed_or_sent_raw(self):
        with patch.object(self.service.repository, "fetch_candidates", side_effect=RuntimeError("private database URI")):
            with self.assertRaisesRegex(RuntimeError, "private database URI"):
                self.service.generate(self.request)
        self.assertTrue(all(span.updates[-1] == {"level": "ERROR", "status_message": "RuntimeError"}
                            for span in self.recording.spans))
        self.assertNotIn("private database URI", repr([span.updates for span in self.recording.spans]))

    def test_telemetry_update_and_close_failures_are_isolated(self):
        @contextmanager
        def broken_context(**kwargs):
            span = RecordingSpan(kwargs)
            span.update = lambda **updates: (_ for _ in ()).throw(RuntimeError("update failed"))
            yield span
            raise RuntimeError("close failed")
        with patch.object(self.recording, "start_as_current_observation", side_effect=broken_context):
            self.assertEqual(self.create()["status"], "complete")


if __name__ == "__main__":
    unittest.main()
