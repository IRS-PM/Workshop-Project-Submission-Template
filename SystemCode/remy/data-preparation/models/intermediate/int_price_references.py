import ast
import math


def model(dbt, session):
    dbt.config(materialized="table")
    session.execute("""
        create or replace temp table parsed_price_references (
            source_fdc_id bigint,
            price_ref varchar,
            priced_name varchar,
            reference_price_minor bigint,
            parse_status varchar,
            rejection_reason varchar,
            source_snapshot_id varchar
        )
    """)

    relation = dbt.ref("stg_price_mapped_nutrients")
    columns = {name: i for i, name in enumerate(relation.columns)}
    output = []
    while rows := relation.fetchmany(1000):
        for row in rows:
            fdc_id = row[columns["fdc_id"]]
            raw = row[columns["item_prices"]]
            snapshot = row[columns["source_snapshot_id"]]
            try:
                parsed = ast.literal_eval(raw or "{}")
                if not isinstance(parsed, dict):
                    raise ValueError("not_a_dictionary")
                if any(
                    not isinstance(key, str)
                    or not key.strip()
                    or isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value <= 0
                    or value * 100 > 9_223_372_036_854_775_807
                    for key, value in parsed.items()
                ):
                    raise ValueError("invalid_key_or_price")
            except (SyntaxError, ValueError, TypeError, MemoryError) as error:
                reason = str(error) if isinstance(error, ValueError) else "malformed_python_literal"
                output.append((fdc_id, None, None, None, "rejected", reason, snapshot))
                continue

            for key, value in parsed.items():
                name = key.strip()
                output.append((
                    fdc_id,
                    f"span:{fdc_id}:{name}",
                    name,
                    round(float(value) * 100),
                    "accepted",
                    None,
                    snapshot,
                ))

    session.executemany("insert into parsed_price_references values (?, ?, ?, ?, ?, ?, ?)", output)
    return session.table("parsed_price_references")
