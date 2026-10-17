
# scripts/create_indexes.py

from app.db import get_db

COLLECTIONS = [
    "users", "categories", "products", "orders", "reviews"
]


def drop_all_indexes(db):
    """Drop all indexes except MongoDB's required _id index."""
    for name in COLLECTIONS:
        db[name].drop_indexes()
        print(f"Dropped non-_id indexes: {name}")


def create_all_indexes(db):
    """Create the project's final index set."""

    indexes = [
        ("users", [("email", 1)], "users_email_unique", {"unique": True}),

        (
            "products",
            [("category_id", 1)],
            "products_category_id",
            {},
        ),

        (
            "products",
            [("name", "text"), ("tags", "text")],
            "products_name_tags_text",
            {},
        ),

        (
            "orders",
            [("user_id", 1), ("created_at", -1)],
            "orders_user_created_desc",
            {},
        ),
        (
            "orders",
            [("created_at", 1)],
            "orders_created_at",
            {},
        ),
        (
            "orders",
            [("items.product_id", 1)],
            "orders_item_product",
            {},
        ),

        (
            "reviews",
            [("product_id", 1)],
            "reviews_product_id",
            {},
        ),
        (
            "reviews",
            [("user_id", 1), ("product_id", 1)],
            "reviews_user_product_unique",
            {"unique": True},
        ),
    ]

    for collection_name, keys, name, options in indexes:
        index_name = db[collection_name].create_index(
            keys, name=name, **options
        )
        print(f"Created {collection_name}.{index_name}")


def print_indexes(db):
    """Display every index currently present."""
    print("\n=== Current indexes ===")

    for name in COLLECTIONS:
        print(f"\n{name}:")
        for index in db[name].list_indexes():
            print(
                f"  {index['name']}: "
                f"{dict(index['key'])}"
            )


def main():
    db = get_db()
    create_all_indexes(db)
    print_indexes(db)


if __name__ == "__main__":
    main()
