
# scripts/benchmark_indexes.py

import statistics
from datetime import datetime, timezone
from pathlib import Path

from pymongo.errors import OperationFailure

from app.db import get_db
from scripts.create_indexes import (
    COLLECTIONS,
    create_all_indexes,
    drop_all_indexes,
)

REPEATS = 5


def collect_stages(node):
    """Collect stage names from nested MongoDB query-plan objects."""
    stages = []

    if isinstance(node, dict):
        if isinstance(node.get("stage"), str):
            stages.append(node["stage"])

        for key, value in node.items():
            if key in {"inputStage", "inputStages", "queryPlan",
                       "winningPlan", "shards", "children"}:
                stages.extend(collect_stages(value))

    elif isinstance(node, list):
        for item in node:
            stages.extend(collect_stages(item))

    return stages


def explain_find(
    db, collection_name, filter_doc, sort=None,
    projection=None, limit=None
):
    """Run explain and return execution statistics."""
    find_command = {
        "find": collection_name,
        "filter": filter_doc,
    }

    if sort:
        find_command["sort"] = sort
    if projection:
        find_command["projection"] = projection
    if limit is not None:
        find_command["limit"] = limit

    result = db.command({
        "explain": find_command,
        "verbosity": "executionStats",
    })

    stats = result["executionStats"]
    plan = result["queryPlanner"]["winningPlan"]

    return {
        "docs": stats.get("totalDocsExamined", 0),
        "keys": stats.get("totalKeysExamined", 0),
        "returned": stats.get("nReturned", 0),
        "times": stats.get("executionTimeMillis", 0),
        "stages": sorted(set(collect_stages(plan))),
    }


def benchmark(
    db, label, collection_name, filter_doc, sort=None,
    projection=None, limit=None
):
    """Repeat explain five times and return median statistics."""
    runs = [
        explain_find(
            db, collection_name, filter_doc,
            sort=sort, projection=projection, limit=limit,
        )
        for _ in range(REPEATS)
    ]

    return {
        "query": label,
        "docs": runs[-1]["docs"],
        "keys": runs[-1]["keys"],
        "returned": runs[-1]["returned"],
        "median_ms": round(
            statistics.median(run["times"] for run in runs), 2
        ),
        "stages": ", ".join(runs[-1]["stages"]) or "Unknown",
        "note": "",
    }


def text_search_check(db):
    """Show the error without a text index, then benchmark $text."""
    filter_doc = {"$text": {"$search": "wireless"}}

    try:
        db.command({
            "explain": {
                "find": "products",
                "filter": filter_doc,
            },
            "verbosity": "executionStats",
        })
        return "Unexpectedly succeeded without a text index"
    except OperationFailure as error:
        return f"Rejected without text index (code {error.code})"


def write_markdown(rows, text_before, output_path):
    """Save benchmark results as a Markdown table."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# MongoDB Index Benchmark Results",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"- Explain repetitions per query: {REPEATS}",
        "- Timing: median of executionTimeMillis",
        "- Primary evidence: documents examined and query-plan stages",
        "",
        f"**Text-search baseline:** {text_before}",
        "",
        "| Query / state | Docs examined | Keys examined | Returned | Median ms | Stages | Notes |",
        "|---|---:|---:|---:|---:|---|---|",
    ]

    for row in rows:
        lines.append(
            f"| {row['query']} | {row['docs']} | {row['keys']} | "
            f"{row['returned']} | {row['median_ms']} | "
            f"{row['stages']} | {row['note']} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- COLLSCAN means MongoDB scanned collection documents.",
        "- IXSCAN means MongoDB scanned index entries.",
        "- A covered query can return results from an index without "
        "reading collection documents.",
        "- Execution time is environment-dependent; examined counts "
        "are generally more useful for comparing plans.",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved report: {output_path}")


def main():
    db = get_db()

    sample_order = db.orders.find_one({}, {"_id": 0, "user_id": 1})
    sample_product = db.products.find_one(
        {}, {"_id": 0, "category_id": 1}
    )

    if not sample_order or not sample_product:
        raise RuntimeError("Seed data is missing. Run the seed script first.")

    user_id = sample_order["user_id"]
    category_id = sample_product["category_id"]

    september_start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    october_start = datetime(2026, 10, 1, tzinfo=timezone.utc)

    user_filter = {"user_id": user_id}
    latest_sort = {"created_at": -1}
    september_filter = {
        "created_at": {"$gte": september_start, "$lt": october_start}
    }
    category_filter = {"category_id": category_id}
    regex_filter = {
        "name": {"$regex": "wireless", "$options": "i"}
    }

    rows = []

    print("Dropping existing non-_id indexes...")
    drop_all_indexes(db)

    # Record the $text error before a text index exists.
    text_before = text_search_check(db)
    print(f"$text without index: {text_before}")

    # Baseline: no secondary indexes.
    rows.append(benchmark(
        db, "1a. User orders — no indexes",
        "orders", user_filter,
    ))
    rows.append(benchmark(
        db, "2a. Latest 10 — no indexes",
        "orders", user_filter, sort=latest_sort, limit=10,
    ))
    rows.append(benchmark(
        db, "3a. September orders — no indexes",
        "orders", september_filter,
    ))
    rows.append(benchmark(
        db, "4a. Products by category — no indexes",
        "products", category_filter,
    ))
    rows.append(benchmark(
        db, "5a. Regex wireless — no indexes",
        "products", regex_filter,
    ))

    # Intermediate state: user_id index only for latest-order comparison.
    db.orders.create_index([("user_id", 1)], name="temp_user_id")
    rows.append(benchmark(
        db, "2b. Latest 10 — user_id only",
        "orders", user_filter, sort=latest_sort, limit=10,
    ))
    db.orders.drop_index("temp_user_id")

    # Final index set.
    create_all_indexes(db)

    rows.append(benchmark(
        db, "1b. User orders — final indexes",
        "orders", user_filter,
    ))
    rows.append(benchmark(
        db, "2c. Latest 10 — compound index",
        "orders", user_filter, sort=latest_sort, limit=10,
    ))
    rows.append(benchmark(
        db, "3b. September orders — final indexes",
        "orders", september_filter,
    ))
    rows.append(benchmark(
        db, "4b. Products by category — final indexes",
        "products", category_filter,
    ))

    regex_row = benchmark(
        db, "5b. Regex wireless — final indexes",
        "products", regex_filter,
    )
    regex_row["note"] = "Unanchored regex; text index does not accelerate it"
    rows.append(regex_row)

    rows.append(benchmark(
        db, "5c. $text wireless — text index",
        "products", {"$text": {"$search": "wireless"}},
    ))

    covered_row = benchmark(
        db, "6. Covered user history query",
        "orders",
        user_filter,
        projection={"_id": 0, "user_id": 1, "created_at": 1},
    )
    covered_row["note"] = "Expect docs examined = 0"
    rows.append(covered_row)

    output_path = (
        Path(__file__).resolve().parents[1]
        / "docs" / "index_benchmark_results.md"
    )
    write_markdown(rows, text_before, output_path)

    print("\n=== Benchmark summary ===")
    for row in rows:
        print(
            f"{row['query']}: docs={row['docs']}, "
            f"keys={row['keys']}, returned={row['returned']}, "
            f"median={row['median_ms']} ms, stages={row['stages']}"
        )

    print("\nFinal indexes:")
    for name in COLLECTIONS:
        print(f"\n{name}:")
        for index in db[name].list_indexes():
            print(f"  {index['name']}: {dict(index['key'])}")


if __name__ == "__main__":
    main()
