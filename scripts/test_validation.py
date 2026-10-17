
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import WriteError

from app.db import get_db


db = get_db()

valid_user_id = ObjectId()
valid_product_id = ObjectId()
now = datetime.now(timezone.utc)

# Each document is invalid for a different reason.
tests = [
    (
        "Invalid order status",
        db.orders,
        {
            "user_id": valid_user_id,
            "status": "delivred",
            "created_at": now,
            "items": [{
                "product_id": valid_product_id,
                "name": "Wireless Mouse",
                "price": 799.0,
                "qty": 1,
            }],
            "total": 799.0,
        },
    ),
    (
        "Empty order items",
        db.orders,
        {
            "user_id": valid_user_id,
            "status": "placed",
            "created_at": now,
            "items": [],
            "total": 0.0,
        },
    ),
    (
        "Invalid review rating",
        db.reviews,
        {
            "user_id": valid_user_id,
            "product_id": valid_product_id,
            "rating": 7,
            "created_at": now,
        },
    ),
]

for description, collection, document in tests:
    try:
        collection.insert_one(document)
        print(f"FAIL: {description} was accepted")
    except WriteError:
        print(f"PASS: {description} was rejected")
