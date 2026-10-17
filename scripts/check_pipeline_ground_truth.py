"""
Checks pipelines 4 to 8 on the REAL seeded data by recomputing every answer
in plain Python from the raw documents and comparing.

Why this matters: tests/test_pipelines.py proves the pipelines on 4 tiny
orders. This proves them on 50,000. Two completely different code paths
(MongoDB aggregation vs a Python loop) agreeing is strong evidence.

Run from the project root (after seeding):
    .\\venv\\Scripts\\python.exe -m scripts.check_pipeline_ground_truth
"""

import sys
from collections import defaultdict
from datetime import datetime

from app.db import get_db
from app.pipelines.registry import run_pipeline

failures = 0


def check(label, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} | {label}" + (f" | {detail}" if detail else ""))


def naive(dt):
    """PyMongo returns naive UTC datetimes; make comparisons consistent."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def band_of(value, boundaries):
    """Same rule as $bucket: lower bound inclusive, upper bound exclusive."""
    for low, high in zip(boundaries, boundaries[1:]):
        if low <= value < high:
            return low
    return "other"


def main():
    db = get_db()
    orders = list(db.orders.find({}, {"status": 1, "created_at": 1, "total": 1, "items": 1}))
    products = list(db.products.find({}, {"name": 1, "stock": 1, "price": 1}))
    reviews = list(db.reviews.find({}, {"product_id": 1, "rating": 1}))

    # ------------------------------------------------------------------
    print("\n=== 5. order_status_summary (Jan 1 to Oct 16) ===")
    start, end = datetime(2026, 1, 1), datetime(2026, 10, 16)
    expected = defaultdict(lambda: [0, 0.0])
    for o in orders:
        if start <= naive(o["created_at"]) < end:
            expected[o["status"]][0] += 1
            expected[o["status"]][1] += o["total"]
    rows = run_pipeline(db, "order_status_summary", {"start": start, "end": end})
    actual = {r["status"]: [r["order_count"], r["total_value"]] for r in rows}
    check("counts and values per status match a Python recount",
          actual == {k: [v[0], round(v[1], 2)] for k, v in expected.items()},
          str({k: v[0] for k, v in actual.items()}))
    check("sorted by order_count, highest first",
          [r["order_count"] for r in rows] == sorted((r["order_count"] for r in rows), reverse=True))

    # ------------------------------------------------------------------
    print("\n=== 6. low_stock_alert (threshold 10) ===")
    expected_low = sorted((p["stock"], p["name"]) for p in products if p["stock"] < 10)
    rows = run_pipeline(db, "low_stock_alert", {"threshold": 10})
    check("same products as a Python filter, lowest stock first",
          [(r["stock"], r["name"]) for r in rows] == expected_low)
    check("exactly 12 products (the seed made 12 low-stock products)", len(rows) == 12, f"got {len(rows)}")

    # ------------------------------------------------------------------
    print("\n=== 7. price_band_distribution ===")
    boundaries = [0, 500, 1000, 2500, 5000, 10000, 20000]
    expected_bands = defaultdict(int)
    for p in products:
        expected_bands[band_of(p["price"], boundaries)] += 1
    rows = run_pipeline(db, "price_band_distribution", {})
    actual_bands = {r["price_band"]: r["product_count"] for r in rows}
    check("band counts match a Python bucketing", actual_bands == dict(expected_bands), str(actual_bands))
    check("bands add up to every product", sum(actual_bands.values()) == len(products),
          f"{sum(actual_bands.values())} of {len(products)}")

    # ------------------------------------------------------------------
    print("\n=== 4. product_ratings (min_reviews 10, limit 10) ===")
    per_product = defaultdict(list)
    for r in reviews:
        per_product[r["product_id"]].append(r["rating"])
    ranked = sorted(
        ((pid, sum(v) / len(v), len(v)) for pid, v in per_product.items() if len(v) >= 10),
        key=lambda t: (-t[1], -t[2], t[0]),
    )[:10]
    rows = run_pipeline(db, "product_ratings", {"min_reviews": 10, "limit": 10})
    check("same products in the same order as a Python ranking",
          [r["product_id"] for r in rows] == [t[0] for t in ranked])
    check("average ratings match (within rounding)",
          all(abs(r["average_rating"] - t[1]) < 0.0051 for r, t in zip(rows, ranked)))
    check("every product has at least 10 reviews", all(r["review_count"] >= 10 for r in rows))

    # ------------------------------------------------------------------
    print("\n=== 8. dashboard_summary (September 2026) ===")
    start, end = datetime(2026, 9, 1), datetime(2026, 10, 1)
    delivered = [o for o in orders
                 if o["status"] == "delivered" and start <= naive(o["created_at"]) < end]
    revenue = sum(o["total"] for o in delivered)

    result = run_pipeline(db, "dashboard_summary", {"start": start, "end": end})
    check("returns exactly one document", len(result) == 1)
    dash = result[0]

    check("revenue and order count match Python",
          dash["totals"]["revenue"] == round(revenue, 2)
          and dash["totals"]["order_count"] == len(delivered),
          f"{dash['totals']['revenue']:,.0f} revenue, {dash['totals']['order_count']:,} orders")
    check("average order value matches",
          abs(dash["totals"]["average_order_value"] - revenue / len(delivered)) < 0.0051)

    trend = run_pipeline(db, "monthly_revenue_trend", {"start": start, "end": end})
    check("dashboard totals equal monthly_revenue_trend for the same month",
          len(trend) == 1
          and trend[0]["revenue"] == dash["totals"]["revenue"]
          and trend[0]["order_count"] == dash["totals"]["order_count"])

    product_revenue = defaultdict(float)
    for o in delivered:
        for item in o["items"]:
            product_revenue[item["product_id"]] += item["price"] * item["qty"]
    top5 = sorted(product_revenue.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    check("top 5 products match a Python ranking",
          [(r["product_id"], r["revenue"]) for r in dash["top_products"]]
          == [(pid, round(rev, 2)) for pid, rev in top5])

    expected_sizes = defaultdict(int)
    for o in delivered:
        expected_sizes[band_of(o["total"], boundaries)] += 1
    size_rows = dash["order_size"]
    key = "order_size_band" if size_rows and "order_size_band" in size_rows[0] else "price_band"
    actual_sizes = {r[key]: r["order_count"] for r in size_rows}
    check("order-size bands match a Python bucketing", actual_sizes == dict(expected_sizes), str(actual_sizes))
    check("order-size bands add up to every delivered order",
          sum(actual_sizes.values()) == len(delivered))

    # ------------------------------------------------------------------
    print("\n=== Empty range behaviour ===")
    empty = {"start": datetime(2025, 1, 1), "end": datetime(2025, 2, 1)}
    check("order_status_summary returns []", run_pipeline(db, "order_status_summary", empty) == [])
    dash_empty = run_pipeline(db, "dashboard_summary", empty)
    check("dashboard_summary returns one document of zeros and empty lists",
          len(dash_empty) == 1
          and dash_empty[0]["totals"]["order_count"] == 0
          and dash_empty[0]["top_products"] == [])

    print(f"\n{'All checks passed.' if not failures else f'{failures} check(s) FAILED.'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()