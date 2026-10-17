
# scripts/setup_collections.py

from app.db import get_db
from app.schemas.validators import (
    users_validator,
    categories_validator,
    products_validator,
    orders_validator,
    reviews_validator,
)


def setup_collections():
    db = get_db()

    validators = {
        "users": users_validator,
        "categories": categories_validator,
        "products": products_validator,
        "orders": orders_validator,
        "reviews": reviews_validator,
    }

    existing_collections = set(db.list_collection_names())

    for name, validator in validators.items():
        if name in existing_collections:
            db.drop_collection(name)
            print(f"Dropped existing collection: {name}")

        db.create_collection(
            name,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )

        print(f"Created collection with validation: {name}")

    print("\nAll five collections are ready!")


if __name__ == "__main__":
    setup_collections()
