"""Live Compose check. Emits one clearly labeled synthetic trace with all three metrics."""

import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from langfuse import Langfuse

from api.features.plan.metrics import ranking_metrics


def main():
    config = dotenv_values(Path(__file__).resolve().parents[1] / ".env.nonprod")
    base_url = "http://localhost:" + config["LANGFUSE_PORT"]
    auth = (config["LANGFUSE_PUBLIC_KEY"], config["LANGFUSE_SECRET_KEY"])
    with httpx.Client(base_url=base_url, timeout=30, follow_redirects=True) as dashboard:
        session = dashboard.get("/api/auth/session")
        session.raise_for_status()
        assert session.json().get("user", {}).get("email") == config["LANGFUSE_INIT_USER_EMAIL"], "Passwordless session failed"
        page = dashboard.get("/")
        assert page.status_code == 200 and "/auth/sign-in" not in page.url.path, "Dashboard requires login"
        print("Passwordless dashboard verified without user credentials or cookies.")
    metrics = ranking_metrics(["fixture-a", "fixture-b", "fixture-c"],
                              {"fixture-a": 3, "fixture-b": 2, "fixture-c": 0})
    client = Langfuse(public_key=auth[0], secret_key=auth[1], base_url=base_url,
                      environment="integration-test", timeout=5)
    try:
        assert client.auth_check(), "Local Langfuse project authentication failed"
        with client.start_as_current_observation(
            name="langfuse-compose-smoke",
            metadata={"synthetic": True, "purpose": "Docker wiring check, NOT human relevance evaluation"},
        ) as span:
            trace_id = span.trace_id
            span.update(output={"check": "three ranking metrics"})
        for name, value in metrics.items():
            client.create_score(trace_id=trace_id, name=name, value=value, data_type="NUMERIC",
                                comment="Synthetic fixture, not human grades or production quality",
                                metadata={"judge": "synthetic_fixture", "synthetic": True})
        client.flush()
        with httpx.Client(base_url=base_url, auth=auth, timeout=5) as http:
            for _ in range(60):
                response = http.get("/api/public/traces/" + trace_id)
                if response.status_code == 200:
                    scores = {score["name"]: score["value"] for score in response.json().get("scores", [])}
                    if all(abs(scores.get(name, -1) - value) < 1e-9 for name, value in metrics.items()):
                        print(f"Local Langfuse trace and all three scores verified: {trace_id}")
                        print("Test data is explicitly labeled synthetic; no human judgments fabricated.")
                        return
                time.sleep(2)
        raise RuntimeError("Trace/scores not queryable after 120 seconds; inspect Langfuse worker logs")
    finally:
        client.shutdown()


if __name__ == "__main__":
    main()
