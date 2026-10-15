import json

import pytest

from api.features.plan import judge_eval
from api.features.plan.evaluation import evaluation_db
from api.features.plan.judge_eval import ensure_judge_table, judge_snapshot


class CountingJudge:
    model = "jev-test"

    def __init__(self, scores):
        self.scores = scores
        self.calls = 0

    def close(self):
        return None

    def ask(self, state, questions):
        self.calls += 1
        return {"fit": {"type": "score", "score": self.scores[state["recipe"]["recipe_id"]],
                        "probabilities": {}}}


def snapshot(*ids):
    return {"request": {"horizon_days": 1}, "ranking_version": "nutrient-deviation-v1", "candidates": [
        {"recipe_id": rid, "title": rid, "nutrients": {}, "ingredients": [], "instructions": None}
        for rid in ids]}


def test_judge_results_are_cached_in_the_evaluation_db(tmp_path, monkeypatch):
    monkeypatch.setenv("REMY_EVALUATION_DB", str(tmp_path / "evals.sqlite3"))
    judge = CountingJudge({"A": 2.0, "B": 1.0})
    with evaluation_db() as db:
        ensure_judge_table(db)
        first = judge_snapshot(db, judge, "ev1", snapshot("A", "B"))
        second = judge_snapshot(db, judge, "ev1", snapshot("A", "B"))
    assert {k: v["score"] for k, v in first.items()} == {"A": 2.0, "B": 1.0}
    assert second == first
    assert judge.calls == 2, "the second pass must read the cache"


def test_eval_refuses_to_run_without_a_key(monkeypatch, capsys):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    assert judge_eval.main([]) == 2
    assert "JEV_API_KEY" in capsys.readouterr().err


def test_eval_judges_stored_plans_without_human_grades(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setenv("REMY_EVALUATION_DB", str(tmp_path / "evals.sqlite3"))
    with evaluation_db() as db:
        db.execute("INSERT INTO ranking_evaluations (id, trace_id, snapshot) VALUES (?, ?, ?)",
                   ("ev1", "trace1", json.dumps(snapshot("A", "B", "C"))))
    monkeypatch.setattr(judge_eval, "JevClient", lambda key: CountingJudge({"A": 3.0, "B": 0.0, "C": 2.0}))
    monkeypatch.setattr(judge_eval, "enqueue_trace_scores", lambda *args, **kwargs: True)
    out = tmp_path / "report.json"
    assert judge_eval.main(["--out", str(out)]) == 0
    report = json.loads(out.read_text())
    assert report["plans"] == 1
    assert report["scores_pushed_to_langfuse"] == 1
    assert report["per_plan"][0]["nDCG@3"] == pytest.approx(0.9558, abs=1e-3)
