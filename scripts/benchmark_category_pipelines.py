

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from bson import json_util

from app.db import get_db
from app.pipelines.analytics import (
    revenue_by_category,
    revenue_by_category_v2,
)

RUNS = 5
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def run_explain(db, pipeline):
    return db.command({
        "explain": {
            "aggregate": "orders",
            "pipeline": pipeline,
            "cursor": {},
        },
        "verbosity": "executionStats",
    })


def parse_explain(explain):
    """
    Pull the numbers we care about out of an aggregate explain.

    Bug fixed here: explain output echoes our own pipeline under "command".
    Walking the whole output therefore counted every "$lookup" in the pipeline
    DEFINITION as if it were a stage that ran (2 real + 2 echoed = 4), and the
    echoed copies have no counters, which is why the counters read 0.
    We now skip the echoed command.

    MongoDB reports $lookup work in one of two shapes, depending on version:
      * a stage dict with a "$lookup" key and counters beside it, or
      * an "EQ_LOOKUP" plan stage inside executionStats (pushed down).
    Both are handled.
    """
    plan = {
        key: value for key, value in explain.items()
        if key not in ("command", "serverInfo", "serverParameters")
    }

    stats = {
        "docs_examined": None,
        "keys_examined": None,
        "lookup_stages": 0,
        "lookup_docs_examined": 0,
        "lookup_keys_examined": 0,
        "lookup_collection_scans": 0,
        "lookup_strategies": set(),
        "lookup_indexes": set(),
        "indexes_used": set(),
    }

    def walk(node, in_exec=False):
        if isinstance(node, dict):
            # The first executionStats found belongs to the initial $match
            # (the cursor stage). Keep it and do not overwrite.
            exec_stats = node.get("executionStats")
            if isinstance(exec_stats, dict) and stats["docs_examined"] is None:
                stats["docs_examined"] = exec_stats.get("totalDocsExamined")
                stats["keys_examined"] = exec_stats.get("totalKeysExamined")

            if "$lookup" in node:
                stats["lookup_stages"] += 1
                stats["lookup_docs_examined"] += node.get("totalDocsExamined", 0)
                stats["lookup_keys_examined"] += node.get("totalKeysExamined", 0)
                stats["lookup_collection_scans"] += node.get("collectionScans", 0)
                stats["lookup_indexes"].update(node.get("indexesUsed", []))
            elif in_exec and node.get("stage") == "EQ_LOOKUP":
                # Only count it inside executionStats, otherwise the same stage
                # would be counted again under queryPlanner.winningPlan.
                stats["lookup_stages"] += 1
                stats["lookup_docs_examined"] += node.get(
                    "totalDocsExamined", node.get("docsExamined", 0))
                stats["lookup_keys_examined"] += node.get(
                    "totalKeysExamined", node.get("keysExamined", 0))
                if node.get("strategy"):
                    stats["lookup_strategies"].add(node["strategy"])
                if node.get("indexName"):
                    stats["lookup_indexes"].add(node["indexName"])

            if node.get("stage") == "IXSCAN" and node.get("indexName"):
                stats["indexes_used"].add(node["indexName"])

            for key, value in node.items():
                walk(value, in_exec or key == "executionStats")

        elif isinstance(node, list):
            for value in node:
                walk(value, in_exec)

    walk(plan)

    for key in ("lookup_strategies", "lookup_indexes", "indexes_used"):
        stats[key] = sorted(stats[key])
    return stats


def time_pipeline(db, pipeline):
    """Run the real aggregation RUNS times. Returns (median ms, rows from last run)."""
    timings = []
    rows = []
    for _ in range(RUNS):
        started = time.perf_counter()
        rows = list(db.orders.aggregate(pipeline))
        timings.append((time.perf_counter() - started) * 1000)
    return median(timings), rows


def simplify(rows):
    """Only the fields that matter for comparing results (drops ObjectIds)."""
    return [(row["category"], row["revenue"]) for row in rows]


def fmt(value):
    return "n/a" if value is None else f"{value:,}"


def save_raw_explain(label, explain):
    DOCS_DIR.mkdir(exist_ok=True)
    path = DOCS_DIR / f"explain_raw_{label}.json"
    path.write_text(
        json.dumps(json.loads(json_util.dumps(explain)), indent=2),
        encoding="utf-8",
    )
    return path


def main():
    db = get_db()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)

    versions = {
        "A": ("A - lookup each item", revenue_by_category),
        "B": ("B - group by product first", revenue_by_category_v2),
    }

    report = {}
    for label, (title, builder) in versions.items():
        pipeline = builder(start, end, 20)
        print(f"\n{title}")

        print(f"  timing {RUNS} real runs...")
        median_ms, rows = time_pipeline(db, pipeline)

        print("  running explain once...")
        explain = run_explain(db, pipeline)
        stats = parse_explain(explain)
        raw_path = save_raw_explain(label, explain)

        report[label] = {"title": title, "median_ms": median_ms,
                         "rows": rows, "stats": stats}

        print(f"  median time:             {median_ms:,.0f} ms")
        print(f"  docs examined ($match):  {fmt(stats['docs_examined'])}")
        print(f"  keys examined ($match):  {fmt(stats['keys_examined'])}")
        print(f"  index used by $match:    {stats['indexes_used']}")
        print(f"  $lookup stages:          {stats['lookup_stages']}")
        print(f"  $lookup docs examined:   {fmt(stats['lookup_docs_examined'])}")
        print(f"  $lookup keys examined:   {fmt(stats['lookup_keys_examined'])}")
        print(f"  $lookup collection scans:{fmt(stats['lookup_collection_scans'])}")
        print(f"  $lookup indexes:         {stats['lookup_indexes']}")
        print(f"  $lookup strategies:      {stats['lookup_strategies']}")
        print(f"  raw explain saved to:    {raw_path}")

    a, b = report["A"], report["B"]

    print("\n=== Correctness ===")
    same = simplify(a["rows"]) == simplify(b["rows"])
    print("Both versions return identical results:", "YES" if same else "NO - INVESTIGATE")

    print("\n=== Result (version B) ===")
    for row in b["rows"]:
        print(f"{row['category']:<24}{row['revenue']:>16,.0f}")

    speedup = a["median_ms"] / b["median_ms"] if b["median_ms"] else float("inf")
    print("\n=== Summary ===")
    print(f"A: {a['median_ms']:,.0f} ms   B: {b['median_ms']:,.0f} ms   "
          f"B is {speedup:.1f}x faster")
    print("If the $lookup counters above are still 0, open docs/explain_raw_A.json, "
          "search for 'lookup' or 'LOOKUP', and send me what you find.")

    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "category_pipeline_benchmark.md"
    lines = [
        "# Revenue-by-category pipeline benchmark",
        "",
        f"Date range: {start:%Y-%m-%d} to {end:%Y-%m-%d} (end exclusive), delivered orders only.",
        f"Time = median of {RUNS} real runs. Counters = one explain(executionStats) run.",
        "",
        "| Metric | A: lookup each item | B: group by product first |",
        "|---|---|---|",
        f"| Median time (ms) | {a['median_ms']:,.0f} | {b['median_ms']:,.0f} |",
        f"| Docs examined by $match | {fmt(a['stats']['docs_examined'])} | {fmt(b['stats']['docs_examined'])} |",
        f"| Index used by $match | {', '.join(a['stats']['indexes_used'])} | {', '.join(b['stats']['indexes_used'])} |",
        f"| $lookup stages | {a['stats']['lookup_stages']} | {b['stats']['lookup_stages']} |",
        f"| $lookup docs examined | {fmt(a['stats']['lookup_docs_examined'])} | {fmt(b['stats']['lookup_docs_examined'])} |",
        f"| Identical results | {'yes' if same else 'NO'} | |",
        f"| Speed-up | | {speedup:.1f}x |",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved report: {out}")


if __name__ == "__main__":
    main()