import httpx
import pytest

from api.core.jev import JevClient, JevConfigError, JevError, require_jev_key
from api.features.plan.exceptions import PlanError
from api.features.plan.jev_ranking import (
    RankerUnavailable, GOOD_FIT, JEV_VERSION, RULE_VERSION, jev_rerank, rank_with_mode, ranker_mode,
    ranking_version, validate_ranker_config,
)
from api.features.plan.models import Recipe
from api.features.plan.schemas import PlanRequest


def no_sleep(_):
    return None


def client_with(responses):
    calls = []

    def handler(request):
        calls.append(request)
        return responses.pop(0)
    return JevClient("test-key", model="jev-latest", base_url="https://jev.test",
                     transport=httpx.MockTransport(handler), sleep=no_sleep), calls


OK_ANSWER = {"model": "jev-1.13.0", "answers": {"good_fit": {"type": "noul", "noul": 0.93}},
             "usage": {"input_tokens": 1, "output_tokens": 1}}


def test_missing_key_is_a_config_error(monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    with pytest.raises(JevConfigError):
        require_jev_key()


def test_client_sends_bearer_key_and_the_request_body():
    client, calls = client_with([httpx.Response(200, json=OK_ANSWER)])
    answers = client.ask({"recipe": {}}, {"good_fit": GOOD_FIT})
    assert answers["good_fit"]["noul"] == 0.93
    sent = calls[0]
    assert str(sent.url) == "https://jev.test/v1/systemone"
    assert sent.headers["authorization"] == "Bearer test-key"
    assert b'"model":"jev-latest"' in sent.content


def test_rate_limit_is_retried_then_succeeds():
    client, calls = client_with([httpx.Response(429), httpx.Response(529), httpx.Response(200, json=OK_ANSWER)])
    assert client.ask({}, {"good_fit": GOOD_FIT})["good_fit"]["noul"] == 0.93
    assert len(calls) == 3


def test_rate_limit_that_never_clears_raises():
    client, calls = client_with([httpx.Response(429)] * 4)
    with pytest.raises(JevError):
        client.ask({}, {"good_fit": GOOD_FIT})
    assert len(calls) == 4


def test_auth_failure_is_not_retried():
    client, calls = client_with([httpx.Response(401)])
    with pytest.raises(JevError, match="401"):
        client.ask({}, {"good_fit": GOOD_FIT})
    assert len(calls) == 1


def request_for(meals=1):
    return PlanRequest(horizon_days=1, meals_per_day=meals)


def recipes(*ids):
    return [Recipe(recipe_id=i, title=f"Recipe {i}") for i in ids]


class FakeJev:
    def __init__(self, probabilities):
        self.probabilities = probabilities
        self.model = "jev-test"

    def ask(self, state, questions):
        return {"good_fit": {"type": "noul", "noul": self.probabilities[state["recipe"]["recipe_id"]]}}


def test_mode_defaults_to_rule_and_rejects_unknown_values(monkeypatch):
    monkeypatch.delenv("RANKER_MODE", raising=False)
    assert ranker_mode() == "rule" and ranking_version() == RULE_VERSION
    monkeypatch.setenv("RANKER_MODE", "llm")
    with pytest.raises(ValueError):
        ranker_mode()


def test_jev_mode_without_key_refuses_to_start(monkeypatch):
    monkeypatch.setenv("RANKER_MODE", "jev")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    with pytest.raises(JevConfigError):
        validate_ranker_config()


def test_jev_mode_without_key_fails_the_request_instead_of_falling_back(monkeypatch):
    monkeypatch.setenv("RANKER_MODE", "jev")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    with pytest.raises(RankerUnavailable):
        rank_with_mode(recipes("a", "b"), request_for())


def test_jev_rerank_orders_the_pool_by_probability():
    fake = FakeJev({"a": 0.2, "b": 0.9, "c": 0.5})
    ranked = jev_rerank(recipes("a", "b", "c"), request_for(), fake)
    assert [r.recipe_id for r in ranked] == ["b", "c", "a"]
    assert ranked[0].score == 0.9


def test_jev_rerank_breaks_ties_by_nutrient_order_and_keeps_top_k():
    fake = FakeJev({"a": 0.5, "b": 0.5, "c": 0.9, "d": 0.1})
    ranked = jev_rerank(recipes("a", "b", "c", "d"), request_for(meals=1), fake)
    assert [r.recipe_id for r in ranked] == ["c", "a", "b", "d"]
    assert len(jev_rerank(recipes(*"abcdefg"), request_for(meals=1), FakeJev({c: 0.5 for c in "abcdefg"}))) == 7


def test_jev_failure_during_rerank_is_a_plan_error(monkeypatch):
    monkeypatch.setenv("RANKER_MODE", "jev")
    monkeypatch.setenv("JEV_API_KEY", "test-key")

    class Broken:
        def ask(self, state, questions):
            raise JevError("Jev request failed with HTTP 401")

        def close(self):
            return None
    monkeypatch.setattr("api.features.plan.jev_ranking.JevClient", lambda key: Broken())
    with pytest.raises(RankerUnavailable) as caught:
        rank_with_mode(recipes("a"), request_for())
    assert isinstance(caught.value, PlanError)
    assert caught.value.code == "RANKER_UNAVAILABLE"


def test_jev_mode_versions_the_snapshot(monkeypatch):
    monkeypatch.setenv("RANKER_MODE", "jev")
    assert ranking_version() == JEV_VERSION


from langgraph.checkpoint.memory import MemorySaver

from api.features.plan import judge as judge_module
from api.features.plan.graph import build_plan_graph
from api.features.plan.judge import (
    JUDGE_VERSION, JudgeUnavailable, judge_candidates, judge_grades, judge_metrics, validate_judge_config,
)


class FakeJudgeClient:
    model = "jev-test"

    def __init__(self, *args, **kwargs):
        self.calls = 0

    def ask(self, state, questions):
        self.calls += 1
        return {"fit": {"type": "score", "score": 2.0 + (1 if state["recipe"]["recipe_id"] == "b" else 0),
                        "probabilities": {}}}

    def close(self):
        return None


def test_judge_is_on_by_default(monkeypatch):
    from api.features.plan.judge import judge_mode
    monkeypatch.delenv("JUDGE_MODE", raising=False)
    assert judge_mode() == "jev"


def test_judge_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "off")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    assert judge_candidates(recipes("a"), request_for()) == ({}, {})


def test_judge_mode_jev_without_key_refuses_to_start(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "jev")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    with pytest.raises(JevConfigError):
        validate_judge_config()


def test_judge_mode_jev_without_key_fails_the_plan(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "jev")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    with pytest.raises(JudgeUnavailable):
        judge_candidates(recipes("a"), request_for())


def test_judge_grades_every_candidate_in_the_pool(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "jev")
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setattr(judge_module, "JevClient", FakeJudgeClient)
    judgments, metrics = judge_candidates(recipes("a", "b"), request_for())
    assert set(judgments) == {"a", "b"}
    assert judgments["b"]["score"] == 3.0 and judgments["a"]["score"] == 2.0
    assert JUDGE_VERSION
    # grades a=2, b=3 in pool order [a, b]: nDCG@3 of that order is below 1
    assert set(metrics) == {"nDCG@3", "Precision@3", "pairwise_accuracy"}
    assert 0 < metrics["nDCG@3"] < 1


class PlainService:
    def fetch_candidates(self, request=None):
        return recipes("a", "b")

    def filter_stage(self, recipes_in, request):
        return recipes_in

    def rank_stage(self, recipes_in, request):
        return recipes_in

    def solve(self, recipes_in, request):
        return [recipes_in], []

    def build_response(self, days, relaxations, request):
        return {"days": len(days)}


def test_judge_runs_as_the_last_task_after_generate(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "jev")
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("RANKER_MODE", "rule")
    monkeypatch.setattr(judge_module, "JevClient", FakeJudgeClient)
    graph = build_plan_graph(PlainService(), MemorySaver())
    config = {"configurable": {"thread_id": "run-judge0001"}}
    graph.invoke({"request": request_for()}, config)
    final = graph.get_state(config)
    assert final.next == ()
    assert final.values["response"] == {"days": 1}
    assert set(final.values["judgments"]) == {"a", "b"}
    assert set(final.values["metrics"]) == {"nDCG@3", "Precision@3", "pairwise_accuracy"}


def test_judge_scores_round_half_up_to_integer_grades():
    judgments = {"a": {"score": 2.5}, "b": {"score": 2.49}, "c": {"score": 0.4}, "d": {"score": 3.0}, "e": {"score": 2.9}}
    assert judge_grades(judgments) == {"a": 3, "b": 2, "c": 0, "d": 3, "e": 3}


def test_judge_metrics_on_the_worked_example():
    # judge scores 2.7, 1.1, 2.9, 0.4, 2.2 become grades 3, 1, 3, 0, 2 in this rule order
    judgments = {"A": {"score": 2.7}, "B": {"score": 1.1}, "C": {"score": 2.9}, "D": {"score": 0.4}, "E": {"score": 2.2}}
    metrics = judge_metrics(["A", "B", "C", "D", "E"], judgments)
    assert metrics["Precision@3"] == pytest.approx(2 / 3)
    assert metrics["nDCG@3"] == pytest.approx(0.8622, abs=1e-3)


def test_a_judge_call_failure_does_not_fail_the_plan(monkeypatch):
    monkeypatch.setenv("JUDGE_MODE", "jev")
    monkeypatch.setenv("JEV_API_KEY", "test-key")

    class Outage(FakeJudgeClient):
        def ask(self, state, questions):
            raise JevError("Jev request failed with HTTP 529")

    monkeypatch.setattr(judge_module, "JevClient", Outage)
    assert judge_candidates(recipes("a", "b"), request_for()) == ({}, {})
    graph = build_plan_graph(PlainService(), MemorySaver())
    config = {"configurable": {"thread_id": "run-judge-outage"}}
    graph.invoke({"request": request_for()}, config)
    final = graph.get_state(config)
    assert final.next == () and final.values["response"] == {"days": 1}
