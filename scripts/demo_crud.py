"""
Live demonstration of the CRUD service layer (for the project report screenshots).

Run:   python -m scripts.demo_crud

It builds a throw-away database (mongo_query_router_demo_crud) with the real
validators and indexes, runs Insert / Read / Update / Delete through the
service layer, prints every result, and drops the database at the end.
Your shop_db is never touched.
"""
from pymongo import ASCENDING, DESCENDING, TEXT

from app.db import get_db
from app.schemas.validators import (
    categories_validator, orders_validator, products_validator,
    reviews_validator, users_validator,
)
from app.services.errors import OutOfStock, ServiceError
from app.services.order_service import cancel_order, get_orders_for_user, place_order, update_order_status
from app.services.product_service import add_product, add_product_tag, search_products, update_price
from app.services.review_service import add_review
from app.services.user_service import create_user, delete_user, update_user_city

DEMO_DB = "mongo_query_router_demo_crud"


def build_demo_db():
    client = get_db(DEMO_DB).client
    client.drop_database(DEMO_DB)
    db = get_db(DEMO_DB)
    for name, validator in [("users", users_validator), ("categories", categories_validator),
                            ("products", products_validator), ("orders", orders_validator),
                            ("reviews", reviews_validator)]:
        db.create_collection(name, validator=validator, validationLevel="strict", validationAction="error")
    db.users.create_index([("email", ASCENDING)], unique=True, name="users_email_unique")
    db.products.create_index([("name", TEXT), ("tags", TEXT)], name="products_name_tags_text")
    db.orders.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)], name="orders_user_created_desc")
    db.reviews.create_index([("user_id", ASCENDING), ("product_id", ASCENDING)], unique=True,
                            name="reviews_user_product_unique")
    return db


def title(text):
    print("\n" + "=" * 70 + f"\n{text}\n" + "=" * 70)


def main():
    db = build_demo_db()
    category_id = db.categories.insert_one({"name": "Electronics"}).inserted_id

    title("1. INSERT")
    user = create_user(db, "Asha Verma", "Asha.Verma@Example.com", "Delhi")
    print("create_user  ->", user["name"], "|", user["email"], "(stored lowercase) |", user["city"])
    mouse = add_product(db, "Wireless Mouse", category_id, 800, 5, ["usb", "wireless"])
    print("add_product  ->", mouse["name"], "| price", mouse["price"], "| stock", mouse["stock"])
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 3}])
    print("place_order  -> status:", order["status"], "| total:", order["total"], "| items:", order["items"][0]["name"], "x", order["items"][0]["qty"])
    print("stock after the order:", db.products.find_one({"_id": mouse["_id"]})["stock"], "(5 - 3 = 2)")
    try:
        place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 3}])
    except OutOfStock as error:
        print("second order for 3 units ->", type(error).__name__ + ":", error)
    print("stock unchanged by the failed order:", db.products.find_one({"_id": mouse["_id"]})["stock"])

    title("2. READ")
    history = get_orders_for_user(db, user["_id"], limit=5)
    print("get_orders_for_user ->", len(history), "order(s), newest first; total =", history[0]["total"])
    for hit in search_products(db, "wireless"):
        print("search_products('wireless') ->", hit["name"], "| text score", round(hit["score"], 2))

    title("3. UPDATE")
    print("update_user_city  ->", update_user_city(db, user["_id"], "Mumbai")["city"])
    updated = update_price(db, mouse["_id"], 950)
    print("update_price      -> new product price:", updated["price"])
    print("old order keeps its price snapshot:", db.orders.find_one({"_id": order["_id"]})["items"][0]["price"], "| total", db.orders.find_one({"_id": order["_id"]})["total"])
    add_product_tag(db, mouse["_id"], "gaming")
    print("add_product_tag (twice) ->", add_product_tag(db, mouse["_id"], "gaming")["tags"], "(no duplicate)")
    update_order_status(db, order["_id"], "shipped")
    print("order status      ->", update_order_status(db, order["_id"], "delivered")["status"])
    review = add_review(db, user["_id"], mouse["_id"], 5, "Works well")
    print("add_review (delivered purchase) -> rating", review["rating"])

    title("4. DELETE / CANCEL")
    try:
        delete_user(db, user["_id"])
    except ServiceError as error:
        print("delete_user (has orders) ->", type(error).__name__ + ":", error)
    second = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])
    print("new order placed, stock now:", db.products.find_one({"_id": mouse["_id"]})["stock"])
    cancel_order(db, second["_id"])
    print("cancel_order -> stock restored to:", db.products.find_one({"_id": mouse["_id"]})["stock"])
    spare = create_user(db, "Temp User", "temp@example.com", "Pune")
    print("delete_user (no orders) ->", delete_user(db, spare["_id"]))

    get_db(DEMO_DB).client.drop_database(DEMO_DB)
    print("\nDemo database dropped. shop_db was not touched.")


if __name__ == "__main__":
    main()
