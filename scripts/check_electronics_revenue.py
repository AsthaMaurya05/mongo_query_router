
from datetime import datetime

from app.db import get_db
from app.pipelines.analytics import revenue_by_category_v2


def main():
    db = get_db()

    months = [
        (
            "August 2026",
            datetime(2026, 8, 1),
            datetime(2026, 9, 1),
            33_469_290,
        ),
        (
            "September 2026",
            datetime(2026, 9, 1),
            datetime(2026, 10, 1),
            22_681_366,
        ),
    ]

    print("\n=== Electronics Revenue Verification ===")

    for month, start, end, expected in months:
        pipeline = revenue_by_category_v2(start, end, 20)
        results = list(db.orders.aggregate(pipeline))

        electronics = next(
            (
                row for row in results
                if row.get("category") == "Electronics"
                or row.get("category_name") == "Electronics"
            ),
            None,
        )

        if electronics is None:
            print(f"\n{month}: Electronics row not found.")
            print("Returned categories:", results)
            continue

        # Support either output field name used by the pipeline.
        actual = electronics.get(
            "revenue",
            electronics.get("total_revenue"),
        )

        print(f"\n{month}")
        print(f"Expected revenue: {expected:,.2f}")
        print(f"Actual revenue:   {actual:,.2f}")

        if actual is not None and abs(actual - expected) < 0.01:
            print("Result: PASS")
        else:
            print("Result: CHECK — values do not match.")

    print("\nExpected Electronics revenue falls by about 32.2%")
    print("from August to September.")


if __name__ == "__main__":
    main()
