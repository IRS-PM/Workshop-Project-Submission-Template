import os
from contextlib import asynccontextmanager

from neo4j import GraphDatabase
from psycopg import connect
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from .monitoring import get_client, shutdown_monitoring
from api.features.plan.jev_ranking import validate_ranker_config
from api.features.plan.judge import validate_judge_config

CHECKPOINT_SCHEMA = "langgraph"


def create_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


def create_checkpointer():
    """Postgres checkpoints for plan runs. Without them a run cannot resume, so refuse to start."""
    url = os.getenv("REMY_CHECKPOINT_DB_URL")
    if not url:
        raise RuntimeError("REMY_CHECKPOINT_DB_URL is required: plan runs are checkpointed to Postgres")
    with connect(url, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {CHECKPOINT_SCHEMA}")
    pool = ConnectionPool(url, open=True, kwargs={
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
        "options": f"-c search_path={CHECKPOINT_SCHEMA}",
    })
    saver = PostgresSaver(pool)
    saver.setup()
    return pool, saver


@asynccontextmanager
async def lifespan(app):
    validate_ranker_config()
    validate_judge_config()
    app.state.neo4j_driver = create_driver()
    app.state.checkpoint_pool, app.state.checkpointer = create_checkpointer()
    get_client()
    try:
        yield
    finally:
        try:
            app.state.checkpoint_pool.close()
            app.state.neo4j_driver.close()
        finally:
            shutdown_monitoring()
