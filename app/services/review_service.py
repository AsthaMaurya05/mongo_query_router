from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.services.errors import AlreadyReviewed, NotFound, NotPurchased
from app.services.utils import to_object_id


def add_review(db, user_id, product_id, rating, comment=None):
    """
    Add a review, but only if the user has a delivered order containing
    the product.

    This is the application-level version of the rule the seed script
    followed when generating reviews. The unique index on
    (user_id, product_id) is what stops a second review, even if two
    requests arrive at the same time.
    """
    # Cheap checks first, before touching the database.
    if isinstance(rating, bool) or not isinstance(rating, int):
        raise ValueError("Rating must be an integer from 1 to 5.")

    if not 1 <= rating <= 5:
        raise ValueError("Rating must be an integer from 1 to 5.")

    if comment is not None and not isinstance(comment, str):
        raise ValueError("Comment must be a string or None.")

    user_id = to_object_id(user_id, "User")
    product_id = to_object_id(product_id, "Product")

    if db.users.find_one({"_id": user_id}, {"_id": 1}) is None:
        raise NotFound("User not found.")

    if db.products.find_one({"_id": product_id}, {"_id": 1}) is None:
        raise NotFound("Product not found.")

    delivered_purchase = db.orders.find_one(
        {
            "user_id": user_id,
            "status": "delivered",
            "items.product_id": product_id,
        },
        {"_id": 1},
    )

    if delivered_purchase is None:
        raise NotPurchased(
            "A review requires a delivered order containing this product."
        )

    review = {
        "user_id": user_id,
        "product_id": product_id,
        "rating": rating,
        "created_at": datetime.now(timezone.utc),
    }

    if comment is not None:
        review["comment"] = comment

    try:
        result = db.reviews.insert_one(review)
    except DuplicateKeyError as error:
        raise AlreadyReviewed(
            "You have already reviewed this product."
        ) from error

    return db.reviews.find_one({"_id": result.inserted_id})