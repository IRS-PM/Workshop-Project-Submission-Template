"""The meal-plan workflow as a LangGraph graph.

Each node is a thin call into PlanService, which keeps the trace spans the
evaluation and the monitoring rely on. With a Postgres checkpointer every node's
output is saved as soon as it finishes, so a run that dies part-way resumes from
the last completed node when it is invoked again with the same thread id.
"""
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .judge import judge_candidates
from .state import decode_days, decode_recipes, encode_days, encode_recipes

NODES = ("retrieve", "filter", "rank", "solve", "generate", "judge")


class PlanState(TypedDict, total=False):
    request: Any
    recipes: list
    filtered: list
    candidates: list
    days: list
    relaxations: list
    response: Any
    judgments: dict
    metrics: dict


def build_plan_graph(service, checkpointer=None):
    def retrieve(state: PlanState):
        return {"recipes": encode_recipes(service.fetch_candidates(state["request"]))}

    def filter_(state: PlanState):
        filtered = service.filter_stage(decode_recipes(state["recipes"]), state["request"])
        return {"filtered": encode_recipes(filtered)}

    def rank(state: PlanState):
        ranked = service.rank_stage(decode_recipes(state["filtered"]), state["request"])
        return {"candidates": encode_recipes(ranked)}

    def solve(state: PlanState):
        days, relaxations = service.solve(decode_recipes(state["candidates"]), state["request"])
        return {"days": encode_days(days), "relaxations": relaxations}

    def generate(state: PlanState):
        response = service.build_response(decode_days(state["days"]), state["relaxations"], state["request"])
        return {"response": response}

    def judge(state: PlanState):
        judgments, metrics = judge_candidates(decode_recipes(state["candidates"]), state["request"])
        return {"judgments": judgments, "metrics": metrics}

    builder = StateGraph(PlanState)
    for name, node in zip(NODES, (retrieve, filter_, rank, solve, generate, judge)):
        builder.add_node(name, node)
    builder.add_edge(START, NODES[0])
    for before, after in zip(NODES, NODES[1:]):
        builder.add_edge(before, after)
    builder.add_edge(NODES[-1], END)
    return builder.compile(checkpointer=checkpointer)
