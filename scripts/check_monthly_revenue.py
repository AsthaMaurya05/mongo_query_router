"""
Checks monthly_revenue_trend against the numbers the seed script printed.

The expected values below come from seed_data.py's report (seed 42), which
computes revenue with a separate, simpler query. If the pipeline and the seed
report agree, the pipeline is right. If you change the seed or its settings,
re-run the seed and update EXPECTED_REVENUE from its new report.

Run from the project root:
    .\\venv\\Scripts\\python.exe -m scripts.check_monthly_revenue
"""

import sys
from datetime import datetime

from app.db import get_db
from app.pipelines.registry import run_pipeline

# Delivered revenue by month, copied from the seed report.
EXPECTED_REVENUE = {
    "2026-01": 46_536_242,
    "2026-02": 44_569_442,
    "2026-03": 47_527_760,
    "2026-04": 45_478_490,
    "2026-05": 48_430_428,
    "2026-06": 45_390_297,
    "2026-07": 48_065_561,
    "2026-08": 47_366_476,
    "2026-09": 37_537_323,
    "2026-10": 9_777_623,
}


def main():
    db = get_db()

    results = run_pipeline(
        db,
        "monthly_revenue_trend",
        {
            "start": datetime(2026, 1, 1),
            "end": datetime(2026, 10, 16),
        },
    )

    print("\n=== Monthly Revenue Verification ===")
    failures = 0

    returned_months = [row["month"] for row in results]
    if returned_months != list(EXPECTED_REVENUE):
        failures += 1
        print("FAIL: months returned are not Jan to Oct 2026:", returned_months)

    for row in results:
        expected = EXPECTED_REVENUE.get(row["month"])
        if expected is None:
            failures += 1
            print(f"FAIL | {row['month']} | unexpected month")
            continue

        # The seed report rounds to whole rupees; revenue here is whole too.
        ok = abs(row["revenue"] - expected) < 0.5
        failures += 0 if ok else 1
        print(
            f"{'PASS' if ok else 'FAIL'} | {row['month']} | "
            f"Revenue: {row['revenue']:,.2f} (expected {expected:,}) | "
            f"Orders: {row['order_count']:,} | "
            f"Average order value: {row['average_order_value']:,.2f}"
        )

    if failures:
        print(f"\n{failures} problem(s) found.")
    else:
        print("\nAll months match the seed report.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()