
"""
Pipeline tests on a tiny dataset whose answers were worked out by hand.

Needs MongoDB running. Uses a SEPARATE database (mongo_query_router_test);
shop_db is never touched.

Run from the project root:
    .\\venv\\Scripts\\python.exe -m pytest tests -v
    .\\venv\\Scripts\\python.exe -m tests.test_pipelines
"""

import sys
from datetime import datetime

from bson import ObjectId

from app.db import get_db
from app.pipelines.registry import run_pipeline

TEST_DB = "mongo_query_router_test"

SEPTEMBER = {"start": "2026-09-01", "end": "2026-10-01"}


def get_test_db():
    """Drop and rebuild the isolated test database."""
    get_db(TEST_DB).client.drop_database(TEST_DB)
    db = get_db(TEST_DB)

    electronics, books, fashion = ObjectId(), ObjectId(), ObjectId()
    mouse, book, shirt, laptop = ObjectId(), ObjectId(), ObjectId(), ObjectId()
    u1, u2 = ObjectId(), ObjectId()

    db.categories.insert_many([
        {"_id": electronics, "name": "Electronics"},
        {"_id": books, "name": "Books"},
        {"_id": fashion, "name": "Fashion"},
    ])

    db.products.insert_many([
        {
            "_id": mouse,
            "name": "Mouse",
            "category_id": electronics,
            "price": 800,
            "stock": 5,
        },
        {
            "_id": book,
            "name": "Book",
            "category_id": books,
            "price": 300,
            "stock": 50,
        },
        {
            "_id": shirt,
            "name": "Shirt",
            "category_id": fashion,
            "price": 500,
            "stock": 9,
        },
        {
            "_id": laptop,
            "name": "Laptop",
            "category_id": electronics,
            "price": 20000,
            "stock": 100,
        },
        {
            "_id": ObjectId(),
            "name": "Keyboard",
            "category_id": electronics,
            "price": 1200,
            "stock": 10,
        },
    ])

    db.reviews.insert_many([
        {"product_id": mouse, "rating": 5},
        {"product_id": mouse, "rating": 5},
        {"product_id": mouse, "rating": 4},
        {"product_id": book, "rating": 5},
    ])

    db.users.insert_many([
        {"_id": u1, "name": "User One", "email": "u1@example.com"},
        {"_id": u2, "name": "User Two", "email": "u2@example.com"},
    ])

    def item(pid, name, price, qty):
        return {
            "product_id": pid,
            "name": name,
            "price": price,
            "qty": qty,
        }

    db.orders.insert_many([
        {
            "user_id": u1,
            "status": "delivered",
            "created_at": datetime(2026, 9, 1, 0, 0, 0),
            "items": [
                item(mouse, "Mouse", 800, 2),
                item(book, "Book", 300, 1),
            ],
            "total": 1900,
        },
        {
            "user_id": u2,
            "status": "delivered",
            "created_at": datetime(2026, 9, 9, 10, 0, 0),
            "items": [
                item(mouse, "Mouse", 800, 1),
                item(shirt, "Shirt", 500, 2),
            ],
            "total": 1800,
        },
        {
            "user_id": u1,
            "status": "cancelled",
            "created_at": datetime(2026, 9, 10, 10, 0, 0),
            "items": [item(laptop, "Laptop", 20000, 1)],
            "total": 20000,
        },
        {
            "user_id": u2,
            "status": "delivered",
            "created_at": datetime(2026, 10, 1, 0, 0, 0),
            "items": [item(book, "Book", 300, 1)],
            "total": 300,
        },
    ])

    return db


def test_revenue_by_category_public_and_naive():
    db = get_test_db()

    for name in ("revenue_by_category", "revenue_by_category_naive"):
        rows = run_pipeline(db, name, {**SEPTEMBER, "limit": 3})
        actual = {row["category"]: row["revenue"] for row in rows}

        assert actual == {
            "Electronics": 2400,
            "Fashion": 1000,
            "Books": 300,
        }, f"{name}: {actual}"


def test_revenue_by_category_order_and_limit():
    db = get_test_db()
    rows = run_pipeline(db, "revenue_by_category", {**SEPTEMBER, "limit": 2})

    assert [row["category"] for row in rows] == ["Electronics", "Fashion"]


def test_top_customers():
    db = get_test_db()
    rows = run_pipeline(db, "top_customers", SEPTEMBER)

    actual = [
        (row["email"], row["total_spend"], row["order_count"])
        for row in rows
    ]

    assert actual == [
        ("u1@example.com", 1900, 1),
        ("u2@example.com", 1800, 1),
    ]

    rows = run_pipeline(db, "top_customers", {**SEPTEMBER, "limit": 1})
    assert [row["email"] for row in rows] == ["u1@example.com"]


def test_monthly_revenue_trend():
    db = get_test_db()
    rows = run_pipeline(
        db,
        "monthly_revenue_trend",
        {"start": "2026-09-01", "end": "2026-11-01"},
    )

    actual = [
        (
            row["month"],
            row["revenue"],
            row["order_count"],
            row["average_order_value"],
        )
        for row in rows
    ]

    assert actual == [
        ("2026-09", 3700, 2, 1850),
        ("2026-10", 300, 1, 300),
    ]


def test_order_status_summary():
    db = get_test_db()
    rows = run_pipeline(db, "order_status_summary", SEPTEMBER)

    actual = {
        row["status"]: (row["order_count"], row["total_value"])
        for row in rows
    }

    assert actual == {
        "delivered": (2, 3700),
        "cancelled": (1, 20000),
    }


def test_low_stock_alert():
    db = get_test_db()
    rows = run_pipeline(db, "low_stock_alert", {"threshold": 10})

    assert rows == [
        {"name": "Mouse", "stock": 5, "category": "Electronics"},
        {"name": "Shirt", "stock": 9, "category": "Fashion"},
    ]

def test_product_ratings():
    db = get_test_db()

    rows = run_pipeline(
        db,
        "product_ratings",
        {"min_reviews": 2, "limit": 10},
    )

    assert rows == [
        {
            "product_id": rows[0]["product_id"],
            "product_name": "Mouse",
            "average_rating": 4.67,
            "review_count": 3,
        }
    ]

def test_empty_range_returns_nothing():
    db = get_test_db()
    empty = {"start": "2025-01-01", "end": "2025-02-01"}

    for name in (
        "revenue_by_category",
        "top_customers",
        "monthly_revenue_trend",
    ):
        assert run_pipeline(db, name, empty) == [], name

def test_price_band_distribution():
    db = get_test_db()

    results = run_pipeline(db, "price_band_distribution", {})

    actual = {
        row["price_band"]: row["product_count"]
        for row in results
    }

    assert actual == {
        0: 1,       # Book: ₹300
        500: 2,     # Shirt: ₹500, Mouse: ₹800
        1000: 1,    # Keyboard: ₹1,200
        "other": 1, # Laptop: ₹20,000
    }

def test_dashboard_summary():
    db = get_test_db()

    results = run_pipeline(
        db,
        "dashboard_summary",
        {
            "start": "2026-09-01",
            "end": "2026-10-01",
        },
    )

    assert len(results) == 1
    result = results[0]

    # Only delivered orders in September are included.
    assert result["totals"] == {
        "revenue": 3700,
        "order_count": 2,
        "average_order_value": 1850,
    }

    # Product revenue is price multiplied by quantity.
    products = {
        item["product_name"]: item["revenue"]
        for item in result["top_products"]
    }

    assert products == {
        "Mouse": 2400,
        "Shirt": 1000,
        "Book": 300,
    }

    # Order totals are 1,900 and 1,800.
    bands = {
        item["price_band"]: item["order_count"]
        for item in result["order_size"]
    }

    assert bands == {
        1000: 2,
    }
    
def main():
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]

    failed = 0

    try:
        for name, func in tests:
            try:
                func()
                print(f"PASS: {name}")
            except Exception as error:
                failed += 1
                print(f"FAIL: {name}: {type(error).__name__}: {error}")
    finally:
        get_db(TEST_DB).client.drop_database(TEST_DB)

    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
