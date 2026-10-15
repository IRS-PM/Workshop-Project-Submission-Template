import asyncio
import json
import logging
import re
from collections.abc import Iterable, Iterator

from api.core.errors import ErrorDetail, error_envelope
from api.core.exceptions import AppError
from api.core.monitoring import update_observation
from .narrative import plan_text
from .state import decode_recipes
from .schemas import PlanResponse
from .service import dump, trace_plan, complete_plan

logger = logging.getLogger(__name__)

KEEP_ALIVE_SECONDS = 10.0
KEEP_ALIVE = ": keep-alive\n\n"
FLUSH_WORDS = 100
WORD = re.compile(r"\S+")
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
STAGES = (
    ("loading", "Loading recipes"),
    ("selecting", "Choosing recipes that fit"),
    ("solving", "Balancing your days"),
)


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def progress(step: int) -> str:
    stage, message = STAGES[step - 1]
    return sse("progress", {"stage": stage, "message": message, "step": step, "total": len(STAGES)})


async def keep_alive_until_done(task: asyncio.Task, interval: float):
    while not task.done():
        await asyncio.wait({task}, timeout=interval)
        if not task.done():
            yield KEEP_ALIVE


def in_thread(fn, *args) -> asyncio.Task:
    return asyncio.create_task(asyncio.to_thread(fn, *args))


def _end_of_word(text: str, n: int) -> int | None:
    for count, match in enumerate(WORD.finditer(text), 1):
        if count == n:
            # A word that touches the end of the buffer may continue in the next piece.
            return match.end() if match.end() < len(text) else None
    return None


def word_chunks(pieces: Iterable[str], size: int = FLUSH_WORDS) -> Iterator[str]:
    """Buffer text until it holds `size` words, then flush them. The last chunk may be shorter."""
    buffer = ""
    for piece in pieces:
        buffer += piece
        while (cut := _end_of_word(buffer, size)) is not None:
            yield buffer[:cut]
            buffer = buffer[cut:]
    if buffer.strip():
        yield buffer


async def stream_plan(request, service, graph, run_id: str, keep_alive_seconds: float = KEEP_ALIVE_SECONDS):
    config = {"configurable": {"thread_id": run_id}}
    with trace_plan(request) as span:
        update_observation(span, input=dump(request))
        try:
            yield sse("run", {"run_id": run_id})
            yield progress(1)
            snapshot = await asyncio.to_thread(graph.get_state, config)
            if snapshot.values.get("response") is not None and not snapshot.next:
                final = snapshot.values
            else:
                graph_input = None if snapshot.values else {"request": request}
                final = None
                loop = asyncio.get_running_loop()
                updates = asyncio.Queue()

                def run_graph():
                    try:
                        for update in graph.stream(graph_input, config, stream_mode="updates"):
                            loop.call_soon_threadsafe(updates.put_nowait, ("node", next(iter(update))))
                        loop.call_soon_threadsafe(updates.put_nowait, ("done", None))
                    except BaseException as exc:
                        loop.call_soon_threadsafe(updates.put_nowait, ("error", exc))

                worker = asyncio.create_task(asyncio.to_thread(run_graph))
                while True:
                    try:
                        kind, value = await asyncio.wait_for(updates.get(), keep_alive_seconds)
                    except TimeoutError:
                        yield KEEP_ALIVE
                        continue
                    if kind == "error":
                        raise value
                    if kind == "done":
                        break
                    if value == "retrieve":
                        yield progress(2)
                    elif value == "rank":
                        yield progress(3)
                await worker
                final = (await asyncio.to_thread(graph.get_state, config)).values

            plan = final["response"]
            if isinstance(plan, PlanResponse):
                complete_plan(plan, request, decode_recipes(final["candidates"]), span)
            for chunk in word_chunks(plan_text(plan)):
                yield sse("text", {"text": chunk})
            yield sse("plan", plan.model_dump(mode="json"))
        except AppError as exc:
            update_observation(span, level="ERROR", status_message=type(exc).__name__)
            details = [ErrorDetail(**item) for item in exc.details]
            yield sse("error", error_envelope(exc.code, exc.message, details))
        except Exception as exc:
            update_observation(span, level="ERROR", status_message=type(exc).__name__)
            logger.exception("Plan stream failed")
            yield sse("error", error_envelope("INTERNAL_ERROR", "An unexpected error occurred"))
