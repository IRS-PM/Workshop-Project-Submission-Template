import pytest


@pytest.fixture(autouse=True)
def judge_off_unless_a_test_turns_it_on(monkeypatch):
    # The judge is on by default in the app. Tests that need it set JUDGE_MODE themselves.
    monkeypatch.setenv("JUDGE_MODE", "off")
