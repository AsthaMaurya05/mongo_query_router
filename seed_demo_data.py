#seed_demo_data.py
from datetime import datetime, timezone

from pymongo.errors import PyMongoError

from app.db import client, get_db

DEMO_DB_NAME = "mongo_query_router_api_dev"


def seed_demo_data():
    # Explicitly target the development database.
    # Never use get_db() without a name in this script.
    db = get_db(DEMO_DB_NAME)

    try:
        client.admin.command("ping")

        existing = db.list_collection_names()
        if existing:
            print(f"Safety stop: {DEMO_DB_NAME} already has collections:")
            print(", ".join(existing))
            print("No data was changed. Inspect the database before proceeding.")
            return

        categories = [
            {"_id": "electronics", "name": "Electronics"},
            {"_id": "books", "name": "Books"},
            {"_id": "fashion", "name": "Fashion"},
        ]
        db.categories.insert_many(categories)

        products = [
            {
                "_id": "mouse",
                "name": "Wireless Mouse",
                "category_id": "electronics",
                "price": 800,
                "stock": 5,
            },
            {
                "_id": "book",
                "name": "Python Programming Book",
                "category_id": "books",
                "price": 300,
                "stock": 50,
            },
            {
                "_id": "shirt",
                "name": "Cotton Shirt",
                "category_id": "fashion",
                "price": 500,
                "stock": 9,
            },
            {
                "_id": "laptop",
                "name": "Laptop",
                "category_id": "electronics",
                "price": 20000,
                "stock": 100,
            },
            {
                "_id": "keyboard",
                "name": "Mechanical Keyboard",
                "category_id": "electronics",
                "price": 1200,
                "stock": 10,
            },
        ]
        db.products.insert_many(products)

        users = [
            {"_id": "u1", "name": "User One", "email": "u1@example.com"},
            {"_id": "u2", "name": "User Two", "email": "u2@example.com"},
        ]
        db.users.insert_many(users)

        def utc_date(year, month, day):
            return datetime(year, month, day, tzinfo=timezone.utc)

        orders = [
            {
                "_id": "order1",
                "user_id": "u1",
                "status": "delivered",
                "created_at": utc_date(2026, 9, 1),
                "items": [
                    {"product_id": "mouse", "name": "Wireless Mouse",
                     "price": 800, "qty": 2},
                    {"product_id": "book", "name": "Python Programming Book",
                     "price": 300, "qty": 1},
                ],
                "total": 1900,
            },
            {
                "_id": "order2",
                "user_id": "u2",
                "status": "delivered",
                "created_at": utc_date(2026, 9, 9),
                "items": [
                    {"product_id": "mouse", "name": "Wireless Mouse",
                     "price": 800, "qty": 1},
                    {"product_id": "shirt", "name": "Cotton Shirt",
                     "price": 500, "qty": 2},
                ],
                "total": 1800,
            },
            {
                "_id": "order3",
                "user_id": "u1",
                "status": "cancelled",
                "created_at": utc_date(2026, 9, 10),
                "items": [
                    {"product_id": "laptop", "name": "Laptop",
                     "price": 20000, "qty": 1},
                ],
                "total": 20000,
            },
            {
                "_id": "order4",
                "user_id": "u2",
                "status": "delivered",
                "created_at": utc_date(2026, 10, 1),
                "items": [
                    {"product_id": "book", "name": "Python Programming Book",
                     "price": 300, "qty": 1},
                ],
                "total": 300,
            },
        ]
        db.orders.insert_many(orders)

        reviews = [
            {"_id": "r1", "product_id": "mouse", "rating": 5},
            {"_id": "r2", "product_id": "mouse", "rating": 5},
            {"_id": "r3", "product_id": "mouse", "rating": 4},
            {"_id": "r4", "product_id": "book", "rating": 5},
        ]
        db.reviews.insert_many(reviews)

        print(f"Demo data inserted successfully into: {db.name}")
        for collection in ["categories", "products", "users", "orders", "reviews"]:
            print(f"{collection}: {db[collection].count_documents({})} records")

    except PyMongoError as error:
        print(f"MongoDB error: {error}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    seed_demo_data()
