import math

from pymongo import ReturnDocument

from app.services.errors import NotFound
from app.services.utils import to_object_id


def _check_price(price):
    """A price must be a finite, non-negative number (not a bool, not NaN)."""
    if (
        isinstance(price, bool)
        or not isinstance(price, (int, float))
        or not math.isfinite(price)
        or price < 0
    ):
        raise ValueError("Price must be a non-negative number.")


def add_product(db, name, category_id, price, stock, tags=None):
    """
    Add a product.

    The category must exist. MongoDB will not check that for us, because
    category_id is only a reference, not a foreign key.
    """
    name = name.strip() if isinstance(name, str) else name

    if not isinstance(name, str) or not name:
        raise ValueError("Product name must be a non-empty string.")

    _check_price(price)

    if isinstance(stock, bool) or not isinstance(stock, int) or stock < 0:
        raise ValueError("Stock must be a non-negative integer.")

    if tags is None:
        tags = []

    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValueError("Tags must be a list of strings.")

    category_id = to_object_id(category_id, "Category")

    if db.categories.find_one({"_id": category_id}, {"_id": 1}) is None:
        raise NotFound("Category not found.")

    product = {
        "name": name,
        "category_id": category_id,
        "price": price,
        "stock": stock,
        "tags": list(tags),
    }

    result = db.products.insert_one(product)
    return db.products.find_one({"_id": result.inserted_id})


def update_price(db, product_id, new_price):
    """
    Update the current product price.

    Existing orders keep the price they were placed at, because each order
    item stores its own price snapshot.
    """
    _check_price(new_price)
    product_id = to_object_id(product_id, "Product")

    updated = db.products.find_one_and_update(
        {"_id": product_id},
        {"$set": {"price": new_price}},
        return_document=ReturnDocument.AFTER,
    )

    if updated is None:
        raise NotFound("Product not found.")

    return updated


def add_product_tag(db, product_id, tag):
    """
    Add a tag only if it is not already present.

    $addToSet ignores duplicates; $push would add the same tag again.
    """
    if not isinstance(tag, str) or not tag.strip():
        raise ValueError("Tag must be a non-empty string.")

    product_id = to_object_id(product_id, "Product")

    updated = db.products.find_one_and_update(
        {"_id": product_id},
        {"$addToSet": {"tags": tag.strip()}},
        return_document=ReturnDocument.AFTER,
    )

    if updated is None:
        raise NotFound("Product not found.")

    return updated


def search_products(db, query, limit=10):
    """
    Search product names and tags using the text index.
    Results are sorted by MongoDB's text relevance score.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must be a non-empty string.")

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer.")

    cursor = (
        db.products.find(
            {"$text": {"$search": query.strip()}},
            {"score": {"$meta": "textScore"}},
        )
        .sort([("score", {"$meta": "textScore"})])
        .limit(limit)
    )

    return list(cursor)