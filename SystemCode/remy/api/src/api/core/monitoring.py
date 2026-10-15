"""Optional, fail-open Langfuse tracing. Never send raw requests or exceptions."""

import logging
import os
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client():
    if os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() != "true":
        return None
    if not all(os.getenv(key) for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")):
        logger.warning("Langfuse disabled: missing credentials")
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(timeout=5, sample_rate=1.0)
    except Exception:
        logger.warning("Langfuse initialization failed")
        return None


def update_observation(span, **kwargs):
    if span is not None:
        try:
            span.update(**kwargs)
        except Exception:
            logger.warning("Langfuse observation update failed")


@contextmanager
def observation(name, **metadata):
    stack, span = ExitStack(), None
    try:
        client = get_client()
        if client is not None:
            span = stack.enter_context(client.start_as_current_observation(
                name=name, as_type="span", metadata=metadata,
            ))
    except Exception:
        logger.warning("Langfuse observation start failed")
    try:
        yield span
    except Exception as exc:
        # SDK context exits normally below: no automatic raw exception capture.
        update_observation(span, level="ERROR", status_message=type(exc).__name__)
        raise
    finally:
        try:
            stack.close()
        except Exception:
            logger.warning("Langfuse observation close failed")


def enqueue_trace_scores(trace_id, metrics, *, source, comment, metadata=None):
    """Attach numeric scores to a trace. Score ids are deterministic, so a re-push updates in place."""
    client = get_client()
    if client is None or trace_id is None:
        return False
    try:
        for name, value in metrics.items():
            if value is not None:
                client.create_score(
                    trace_id=trace_id, name=name, value=float(value), data_type="NUMERIC",
                    score_id=str(uuid5(NAMESPACE_URL, f"remy/{trace_id}/{source}/{name}")),
                    comment=comment, metadata={"source": source, **(metadata or {})},
                )
        return True  # Queued, not confirmation of remote delivery.
    except Exception:
        logger.warning("Langfuse score enqueue failed")
        return False


def shutdown_monitoring():
    client = get_client()
    if client is not None:
        try:
            client.shutdown()
        except Exception:
            logger.warning("Langfuse shutdown failed")
