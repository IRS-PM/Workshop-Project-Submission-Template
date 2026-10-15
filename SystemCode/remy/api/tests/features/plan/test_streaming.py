import asyncio
import json
import time
from unittest import mock

from fastapi.testclient import TestClient
from pydantic import BaseModel
from langgraph.checkpoint.memory import MemorySaver

from api.core.exceptions import AppError
from api.features.plan.dependencies import get_plan_service
from api.features.plan.exceptions import PlanInfeasible
from api.features.plan.graph import build_plan_graph
from api.features.plan.models import Recipe
from api.features.plan.service import PlanService
from api.features.plan.schemas import DayResponse, MealResponse, PlanResponse
from api.features.plan.streaming import KEEP_ALIVE, stream_plan, word_chunks
from api.main import app


class FakePlan(BaseModel):
    plan_id: str = "plan_test"
    status: str = "complete"
    days: list = []


def meal(slot, title, calories):
    return MealResponse(slot=slot, recipe_id=f"r_{slot}", title=title, nutrients={"calories": calories},
                        ingredients=[], instructions=None)


def real_plan(horizon_days):
    days = [DayResponse(day=d, meals=[meal("meal_1", "Chickpea Curry", 640), meal("meal_2", "Oat Bowl", 420.4),
                                      meal("meal_3", "Tofu Stir Fry", 510)])
            for d in range(1, horizon_days + 1)]
    return PlanResponse(plan_id="plan_real", status="complete", message="ok", validation_summary={},
                        horizon_totals={}, days=days)


class FakeService:
    def __init__(self, fetch_delay=0.0, solve_error=None, plan=None):
        self.fetch_delay = fetch_delay
        self.solve_error = solve_error
        self.plan = plan or FakePlan()

    def fetch_candidates(self, request=None):
        time.sleep(self.fetch_delay)
        return [Recipe(recipe_id="r_test", title="Test recipe")]

    def select_candidates(self, recipes, request):
        return recipes

    def filter_stage(self, recipes, request):
        return recipes

    def rank_stage(self, recipes, request):
        return recipes

    def solve(self, recipes, request):
        if self.solve_error:
            raise self.solve_error
        return [[recipes[0]]], []

    def build_response(self, days, relaxations, request):
        return self.plan


class EmptyRepository:
    def fetch_candidates(self, request=None):
        return []


def collect(service, keep_alive_seconds=10.0, checkpointer=None, run_id="run-test0001"):
    graph = build_plan_graph(service, checkpointer or MemorySaver())

    async def run():
        return [chunk async for chunk in stream_plan(None, service, graph, run_id, keep_alive_seconds)]
    return asyncio.run(run())


def events(chunks):
    parsed = []
    for chunk in chunks:
        if chunk == KEEP_ALIVE:
            parsed.append(("keep-alive", None))
            continue
        lines = dict(line.split(": ", 1) for line in chunk.strip().split("\n"))
        parsed.append((lines["event"], json.loads(lines["data"])))
    return [item for item in parsed if item[0] != "run"]


def fake_pool():
    return mock.MagicMock()


def test_run_id_is_announced_first():
    first = json.loads(collect(FakeService(), run_id="run-announce1")[0].split("data: ")[1])
    assert first == {"run_id": "run-announce1"}


def test_progress_events_then_the_plan():
    parsed = events(collect(FakeService()))
    assert [name for name, _ in parsed] == ["progress", "progress", "progress", "plan"]
    assert [data["stage"] for _, data in parsed[:3]] == ["loading", "selecting", "solving"]
    assert parsed[0][1] == {"stage": "loading", "message": "Loading recipes", "step": 1, "total": 3}
    assert parsed[-1][1]["plan_id"] == "plan_test"


def test_word_chunks_flush_every_hundred_words_without_splitting_words():
    words = [f"w{i}" for i in range(250)]
    text = " ".join(words) + "\n"
    pieces = [text[i:i + 7] for i in range(0, len(text), 7)]
    chunks = list(word_chunks(pieces))
    assert [len(chunk.split()) for chunk in chunks] == [100, 100, 50]
    assert "".join(chunks) == text
    assert "".join(chunks).split() == words


def test_word_chunks_wait_for_a_word_to_finish_before_flushing():
    assert list(word_chunks(["one two thr", "ee four"], size=3)) == ["one two three", " four"]
    assert list(word_chunks(["one two", " "], size=2)) == ["one two"]
    assert list(word_chunks(["  ", "\n"])) == []


def test_plan_text_streams_in_hundred_word_chunks_before_the_plan():
    parsed = events(collect(FakeService(plan=real_plan(10))))
    names = [name for name, _ in parsed]
    assert names[:3] == ["progress"] * 3 and names[-1] == "plan"
    texts = [data["text"] for name, data in parsed if name == "text"]
    assert len(texts) == 3
    assert [len(text.split()) for text in texts[:-1]] == [100, 100]
    full = "".join(texts)
    assert full.startswith("Day 1: Chickpea Curry (640 kcal), Oat Bowl (420 kcal) and Tofu Stir Fry (510 kcal). "
                           "About 1,570 kcal in all.\nDay 2:")
    assert full.count("\n") == 10
    assert parsed[-1][1]["plan_id"] == "plan_real"


def test_short_plans_flush_their_text_once():
    texts = [data["text"] for name, data in events(collect(FakeService(plan=real_plan(1)))) if name == "text"]
    assert len(texts) == 1 and texts[0].startswith("Day 1:")


def test_slow_steps_send_keep_alive_comments():
    chunks = collect(FakeService(fetch_delay=0.2), keep_alive_seconds=0.03)
    assert chunks.count(KEEP_ALIVE) >= 2
    assert events(chunks)[-1][0] == "plan"


def test_planner_failures_become_an_error_event():
    parsed = events(collect(FakeService(solve_error=PlanInfeasible("No feasible plan after all relaxations"))))
    assert parsed[-1][0] == "error"
    assert parsed[-1][1]["error"]["code"] == "PLAN_INFEASIBLE"
    assert parsed[-1][1]["error"]["message"] == "No feasible plan after all relaxations"


def test_unexpected_failures_hide_details():
    parsed = events(collect(FakeService(solve_error=RuntimeError("neo4j password wrong"))))
    assert parsed[-1][1]["error"]["code"] == "INTERNAL_ERROR"
    assert "neo4j" not in json.dumps(parsed[-1][1])


def test_endpoint_streams_with_event_stream_headers():
    app.dependency_overrides[get_plan_service] = lambda: PlanService(EmptyRepository())
    try:
        with mock.patch("api.core.database.create_checkpointer", return_value=(fake_pool(), MemorySaver())), \
                TestClient(app) as client:
            response = client.post("/api/v1/plan", json={"horizon_days": 1, "meals_per_day": 1})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["connection"] == "keep-alive"
    parsed = events([chunk + "\n\n" for chunk in response.text.strip().split("\n\n")])
    assert [name for name, _ in parsed] == ["progress", "progress", "error"]
    assert parsed[-1][1]["error"]["code"] == "NO_CANDIDATES"


def test_bad_codes_are_rejected_before_the_stream_starts():
    app.dependency_overrides[get_plan_service] = lambda: PlanService(EmptyRepository())
    try:
        with mock.patch("api.core.database.create_checkpointer", return_value=(fake_pool(), MemorySaver())), \
                TestClient(app) as client:
            allergen = client.post("/api/v1/plan", json={"horizon_days": 1, "meals_per_day": 1, "allergies": [{"code": "tree nut"}]})
            dietary = client.post("/api/v1/plan", json={"horizon_days": 1, "meals_per_day": 1, "dietary": [{"code": "keto"}]})
            invalid = client.post("/api/v1/plan", json={"horizon_days": 30, "meals_per_day": 1})
    finally:
        app.dependency_overrides.clear()
    assert (allergen.status_code, allergen.json()["error"]["code"]) == (400, "UNKNOWN_ALLERGEN")
    assert (dietary.status_code, dietary.json()["error"]["code"]) == (400, "UNKNOWN_DIETARY")
    assert (invalid.status_code, invalid.json()["error"]["code"]) == (422, "VALIDATION_ERROR")
    assert all(r.headers["content-type"].startswith("application/json") for r in (allergen, dietary, invalid))


def test_app_errors_keep_their_code_and_details():
    error = AppError("Bad thing", [{"field": "nutrients.0", "issue": "nope"}])
    parsed = events(collect(FakeService(solve_error=error)))
    assert parsed[-1][1]["error"]["details"] == [{"field": "nutrients.0", "issue": "nope"}]


class CrashOnceService(FakeService):
    """Fails in solve on its first call, like a worker that dies mid-run."""

    def __init__(self):
        super().__init__()
        self.fetches = 0
        self.solves = 0

    def fetch_candidates(self, request=None):
        self.fetches += 1
        return [Recipe(recipe_id="r_test", title="Test recipe")]

    def solve(self, recipes, request):
        self.solves += 1
        if self.solves == 1:
            raise RuntimeError("worker died")
        return super().solve(recipes, request)


def test_a_crashed_run_resumes_from_its_last_checkpoint():
    checkpointer = MemorySaver()
    service = CrashOnceService()
    first = events(collect(service, checkpointer=checkpointer, run_id="run-resume01"))
    assert first[-1][0] == "error"
    second = events(collect(service, checkpointer=checkpointer, run_id="run-resume01"))
    assert second[-1][0] == "plan"
    assert service.fetches == 1, "retrieve must not run again after its checkpoint"
    assert service.solves == 2


def test_a_finished_run_returns_its_stored_plan_without_recomputing():
    checkpointer = MemorySaver()
    service = CrashOnceService()
    collect(service, checkpointer=checkpointer, run_id="run-done0001")
    collect(service, checkpointer=checkpointer, run_id="run-done0001")
    again = events(collect(service, checkpointer=checkpointer, run_id="run-done0001"))
    assert again[-1][0] == "plan"
    assert (service.fetches, service.solves) == (1, 2)
