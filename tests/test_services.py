"""
Tests for the CRUD service layer (Step 7).

Run on a real MongoDB (validators and the text index need it):
    python -m pytest tests/test_services.py -v

Every test gets a freshly rebuilt test database with the real validators and
indexes, so a rule that works here also works in shop_db. Each test uses tiny
numbers you can check by hand.
"""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.errors import WriteError

from app.db import get_db
from app.schemas.validators import (
    categories_validator,
    orders_validator,
    products_validator,
    reviews_validator,
    users_validator,
)
from app.services.errors import (
    AlreadyReviewed,
    DuplicateEmail,
    InvalidTransition,
    NotFound,
    NotPurchased,
    OutOfStock,
    UserHasOrders,
)
from app.services.order_service import (
    cancel_order,
    get_order,
    get_orders_for_user,
    place_order,
    update_order_status,
)
from app.services.product_service import (
    add_product,
    add_product_tag,
    search_products,
    update_price,
)
from app.services.review_service import add_review
from app.services.user_service import create_user, delete_user, update_user_city

TEST_DB = "mongo_query_router_service_test"


# --------------------------------------------------------------------------
# Setup helpers
# --------------------------------------------------------------------------
@pytest.fixture
def db():
    """A clean test database: real validators + the same indexes as shop_db."""
    client = get_db(TEST_DB).client
    client.drop_database(TEST_DB)
    database = get_db(TEST_DB)

    for name, validator in [
        ("users", users_validator),
        ("categories", categories_validator),
        ("products", products_validator),
        ("orders", orders_validator),
        ("reviews", reviews_validator),
    ]:
        database.create_collection(
            name,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )

    database.users.create_index([("email", ASCENDING)], unique=True, name="users_email_unique")
    database.products.create_index([("category_id", ASCENDING)], name="products_category_id")
    database.products.create_index(
        [("name", TEXT), ("tags", TEXT)], name="products_name_tags_text"
    )
    database.orders.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)], name="orders_user_created_desc"
    )
    database.reviews.create_index(
        [("user_id", ASCENDING), ("product_id", ASCENDING)],
        unique=True,
        name="reviews_user_product_unique",
    )

    yield database
    client.drop_database(TEST_DB)


def make_user(db, email="a@example.com"):
    return create_user(db, "Asha", email, "Delhi")


def make_category(db, name="Electronics"):
    return db.categories.insert_one({"name": name}).inserted_id


def make_product(db, category_id=None, name="Mouse", price=10, stock=5, tags=None):
    category_id = category_id or make_category(db)
    return add_product(db, name, category_id, price, stock, tags or ["usb"])


def stock_of(db, product):
    return db.products.find_one({"_id": product["_id"]})["stock"]


def deliver(db, order):
    """Walk an order through the legal path placed -> shipped -> delivered."""
    update_order_status(db, order["_id"], "shipped")
    return update_order_status(db, order["_id"], "delivered")


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
def test_create_user_normalises_and_returns_document(db):
    user = create_user(db, "  Asha  ", "  ASHA@Example.COM ", " Delhi ")
    assert user["name"] == "Asha"
    assert user["email"] == "asha@example.com"
    assert user["city"] == "Delhi"
    assert user["joined_at"] is not None


def test_duplicate_email_is_rejected_case_insensitively(db):
    make_user(db, "a@example.com")
    with pytest.raises(DuplicateEmail):
        make_user(db, "A@EXAMPLE.COM")
    assert db.users.count_documents({}) == 1


@pytest.mark.parametrize(
    "name,email,city",
    [("", "a@b.com", "X"), ("A", "not-an-email", "X"), ("A", "a@b.com", ""), (None, "a@b.com", "X")],
)
def test_create_user_rejects_bad_input(db, name, email, city):
    with pytest.raises(ValueError):
        create_user(db, name, email, city)
    assert db.users.count_documents({}) == 0


def test_update_user_city_returns_updated_document(db):
    user = make_user(db)
    updated = update_user_city(db, user["_id"], "Mumbai")
    assert updated["city"] == "Mumbai"
    assert db.users.find_one({"_id": user["_id"]})["city"] == "Mumbai"


def test_update_user_city_accepts_string_id_and_rejects_unknown(db):
    user = make_user(db)
    assert update_user_city(db, str(user["_id"]), "Pune")["city"] == "Pune"
    with pytest.raises(NotFound):
        update_user_city(db, ObjectId(), "Pune")
    with pytest.raises(NotFound):
        update_user_city(db, "not-an-id", "Pune")
    with pytest.raises(NotFound):
        update_user_city(db, None, "Pune")


def test_delete_user_without_orders_works(db):
    user = make_user(db)
    assert delete_user(db, user["_id"]) is True
    assert db.users.count_documents({}) == 0
    with pytest.raises(NotFound):
        delete_user(db, user["_id"])


def test_delete_user_with_orders_is_refused_and_user_stays(db):
    user = make_user(db)
    product = make_product(db)
    place_order(db, user["_id"], [{"product_id": product["_id"], "qty": 1}])

    with pytest.raises(UserHasOrders):
        delete_user(db, user["_id"])

    assert db.users.count_documents({"_id": user["_id"]}) == 1
    assert db.orders.count_documents({"user_id": user["_id"]}) == 1


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
def test_add_product_and_validation(db):
    category_id = make_category(db)
    product = add_product(db, "Mouse", category_id, 10, 5, ["usb"])
    assert product["price"] == 10 and product["stock"] == 5

    with pytest.raises(NotFound):
        add_product(db, "Ghost", ObjectId(), 10, 5)
    for bad in [
        dict(name="", price=10, stock=1),
        dict(name="X", price=-1, stock=1),
        dict(name="X", price=True, stock=1),
        dict(name="X", price=float("nan"), stock=1),
        dict(name="X", price=10, stock=-1),
        dict(name="X", price=10, stock=1.5),
    ]:
        with pytest.raises(ValueError):
            add_product(db, bad["name"], category_id, bad["price"], bad["stock"])
    assert db.products.count_documents({}) == 1


def test_add_product_tag_does_not_duplicate(db):
    product = make_product(db, tags=["usb"])
    add_product_tag(db, product["_id"], "wireless")
    updated = add_product_tag(db, product["_id"], "wireless")
    assert updated["tags"].count("wireless") == 1
    assert sorted(updated["tags"]) == ["usb", "wireless"]
    with pytest.raises(NotFound):
        add_product_tag(db, ObjectId(), "x")


def test_search_products_ranks_by_relevance_and_respects_limit(db):
    category_id = make_category(db)
    add_product(db, "Wireless Mouse", category_id, 10, 1, ["mouse"])
    add_product(db, "Keyboard", category_id, 20, 1, ["wireless"])
    add_product(db, "Notebook", category_id, 5, 1, ["paper"])

    found = search_products(db, "wireless")
    assert {p["name"] for p in found} == {"Wireless Mouse", "Keyboard"}
    assert found[0]["score"] >= found[1]["score"]
    assert len(search_products(db, "wireless", limit=1)) == 1
    assert search_products(db, "zzzz") == []
    with pytest.raises(ValueError):
        search_products(db, "   ")


# --------------------------------------------------------------------------
# Orders: placing
# --------------------------------------------------------------------------
def test_place_order_snapshots_items_and_reduces_stock(db):
    user = make_user(db)
    mouse = make_product(db, name="Mouse", price=10, stock=5)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 3}])

    assert order["status"] == "placed"
    assert order["total"] == 30
    assert order["items"] == [
        {"product_id": mouse["_id"], "name": "Mouse", "price": 10, "qty": 3}
    ]
    assert stock_of(db, mouse) == 2


def test_duplicate_lines_are_merged_before_the_stock_check(db):
    user = make_user(db)
    mouse = make_product(db, stock=5)
    # 3 + 3 = 6 > 5, so this must fail even though each line alone would pass.
    with pytest.raises(OutOfStock):
        place_order(
            db,
            user["_id"],
            [{"product_id": mouse["_id"], "qty": 3}, {"product_id": mouse["_id"], "qty": 3}],
        )
    assert stock_of(db, mouse) == 5
    assert db.orders.count_documents({}) == 0

    order = place_order(
        db,
        user["_id"],
        [{"product_id": mouse["_id"], "qty": 2}, {"product_id": mouse["_id"], "qty": 3}],
    )
    assert order["items"][0]["qty"] == 5 and len(order["items"]) == 1
    assert stock_of(db, mouse) == 0


def test_failure_on_second_line_rolls_back_the_first(db):
    """A has stock 5, B has stock 1. Ordering A x2 and B x3 must change nothing."""
    user = make_user(db)
    category_id = make_category(db)
    a = make_product(db, category_id, name="A", stock=5)
    b = make_product(db, category_id, name="B", stock=1)

    with pytest.raises(OutOfStock):
        place_order(
            db,
            user["_id"],
            [{"product_id": a["_id"], "qty": 2}, {"product_id": b["_id"], "qty": 3}],
        )

    assert stock_of(db, a) == 5
    assert stock_of(db, b) == 1
    assert db.orders.count_documents({}) == 0


def test_unknown_product_rolls_back_earlier_lines(db):
    user = make_user(db)
    a = make_product(db, stock=5)
    with pytest.raises(NotFound):
        place_order(
            db,
            user["_id"],
            [{"product_id": a["_id"], "qty": 2}, {"product_id": ObjectId(), "qty": 1}],
        )
    assert stock_of(db, a) == 5
    assert db.orders.count_documents({}) == 0


def test_failed_order_insert_restores_stock(db, monkeypatch):
    """If the order insert itself fails, the stock taken must be given back."""
    user = make_user(db)
    a = make_product(db, stock=5)

    def boom(*args, **kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(type(db.orders), "insert_one", boom)
    with pytest.raises(RuntimeError):
        place_order(db, user["_id"], [{"product_id": a["_id"], "qty": 2}])
    monkeypatch.undo()

    assert stock_of(db, a) == 5
    assert db.orders.count_documents({}) == 0


@pytest.mark.parametrize(
    "items",
    [None, [], "x", [{"qty": 1}], [{"product_id": "bad", "qty": 1}]],
)
def test_place_order_rejects_bad_items(db, items):
    user = make_user(db)
    with pytest.raises((ValueError, NotFound)):
        place_order(db, user["_id"], items)
    assert db.orders.count_documents({}) == 0


@pytest.mark.parametrize("qty", [0, -1, 1.5, True, "2", None])
def test_place_order_rejects_bad_quantity(db, qty):
    user = make_user(db)
    mouse = make_product(db)
    with pytest.raises(ValueError):
        place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": qty}])
    assert stock_of(db, mouse) == 5


def test_place_order_unknown_user(db):
    mouse = make_product(db)
    with pytest.raises(NotFound):
        place_order(db, ObjectId(), [{"product_id": mouse["_id"], "qty": 1}])
    assert stock_of(db, mouse) == 5


def test_price_snapshot_survives_a_later_price_change(db):
    user = make_user(db)
    mouse = make_product(db, price=10, stock=10)
    first = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 2}])

    update_price(db, mouse["_id"], 25)

    stored = get_order(db, first["_id"])
    assert stored["items"][0]["price"] == 10
    assert stored["total"] == 20

    second = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 2}])
    assert second["items"][0]["price"] == 25
    assert second["total"] == 50


def test_total_is_rounded_to_cents(db):
    user = make_user(db)
    pen = make_product(db, name="Pen", price=0.1, stock=10)
    order = place_order(db, user["_id"], [{"product_id": pen["_id"], "qty": 3}])
    # 0.1 * 3 is 0.30000000000000004 in floating point.
    assert order["total"] == 0.3


def test_concurrent_orders_never_oversell(db):
    """Stock 5, 20 customers each want 1: exactly 5 succeed, 15 get OutOfStock."""
    user = make_user(db)
    mouse = make_product(db, stock=5)
    results = []
    lock = threading.Lock()
    barrier = threading.Barrier(20)

    def worker():
        barrier.wait()
        try:
            place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])
            outcome = "ok"
        except OutOfStock:
            outcome = "out"
        except Exception as error:  # a wrong exception type must fail the test
            outcome = f"unexpected: {error!r}"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 5, results
    assert results.count("out") == 15, results
    assert stock_of(db, mouse) == 0
    assert db.orders.count_documents({}) == 5


# --------------------------------------------------------------------------
# Orders: history and status changes
# --------------------------------------------------------------------------
def test_order_history_is_newest_first_and_limited(db):
    user = make_user(db)
    mouse = make_product(db, stock=10)
    ids = [
        place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])["_id"]
        for _ in range(3)
    ]

    # Force clearly different timestamps: ids[0] oldest ... ids[2] newest.
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for offset, order_id in enumerate(ids):
        db.orders.update_one(
            {"_id": order_id}, {"$set": {"created_at": base + timedelta(days=offset)}}
        )

    latest_two = get_orders_for_user(db, user["_id"], limit=2)
    assert [o["_id"] for o in latest_two] == [ids[2], ids[1]]
    assert len(get_orders_for_user(db, user["_id"])) == 3

    other = make_user(db, "b@example.com")
    assert get_orders_for_user(db, other["_id"]) == []
    with pytest.raises(NotFound):
        get_orders_for_user(db, ObjectId())
    with pytest.raises(ValueError):
        get_orders_for_user(db, user["_id"], limit=0)


def test_legal_status_path(db):
    user = make_user(db)
    mouse = make_product(db)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])
    assert update_order_status(db, order["_id"], "shipped")["status"] == "shipped"
    assert update_order_status(db, order["_id"], "delivered")["status"] == "delivered"


@pytest.mark.parametrize("bad", ["delivered", "placed", "refunded", None])
def test_illegal_transitions_from_placed(db, bad):
    user = make_user(db)
    mouse = make_product(db)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])
    with pytest.raises(InvalidTransition):
        update_order_status(db, order["_id"], bad)
    assert get_order(db, order["_id"])["status"] == "placed"


def test_cancel_restores_stock_exactly_once(db):
    user = make_user(db)
    mouse = make_product(db, stock=5)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 3}])
    assert stock_of(db, mouse) == 2

    cancelled = cancel_order(db, order["_id"])
    assert cancelled["status"] == "cancelled"
    assert stock_of(db, mouse) == 5

    with pytest.raises(InvalidTransition):
        cancel_order(db, order["_id"])
    assert stock_of(db, mouse) == 5  # not 8


def test_cannot_cancel_a_delivered_order(db):
    user = make_user(db)
    mouse = make_product(db, stock=5)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 2}])
    deliver(db, order)

    with pytest.raises(InvalidTransition):
        cancel_order(db, order["_id"])
    assert get_order(db, order["_id"])["status"] == "delivered"
    assert stock_of(db, mouse) == 3


def test_cannot_revive_a_cancelled_order(db):
    user = make_user(db)
    mouse = make_product(db)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])
    cancel_order(db, order["_id"])
    for target in ["placed", "shipped", "delivered"]:
        with pytest.raises(InvalidTransition):
            update_order_status(db, order["_id"], target)


def test_cancel_unknown_order(db):
    with pytest.raises(NotFound):
        cancel_order(db, ObjectId())


def test_concurrent_cancels_restore_stock_once(db):
    user = make_user(db)
    mouse = make_product(db, stock=5)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 3}])
    outcomes = []
    lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            cancel_order(db, order["_id"])
            result = "ok"
        except InvalidTransition:
            result = "rejected"
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert outcomes.count("ok") == 1, outcomes
    assert stock_of(db, mouse) == 5


# --------------------------------------------------------------------------
# Database validators still protect us when the service layer is bypassed
# --------------------------------------------------------------------------
def test_validator_rejects_negative_stock_even_for_a_raw_inc(db):
    mouse = make_product(db, stock=5)
    with pytest.raises(WriteError):
        db.products.update_one({"_id": mouse["_id"]}, {"$inc": {"stock": -10}})
    assert stock_of(db, mouse) == 5


# --------------------------------------------------------------------------
# Reviews
# --------------------------------------------------------------------------
def test_review_requires_a_delivered_purchase(db):
    user = make_user(db)
    mouse = make_product(db)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])

    with pytest.raises(NotPurchased):  # only "placed"
        add_review(db, user["_id"], mouse["_id"], 5)

    update_order_status(db, order["_id"], "shipped")
    with pytest.raises(NotPurchased):  # only "shipped"
        add_review(db, user["_id"], mouse["_id"], 5)

    update_order_status(db, order["_id"], "delivered")
    review = add_review(db, user["_id"], mouse["_id"], 5, "Great")
    assert review["rating"] == 5 and review["comment"] == "Great"


def test_review_for_a_different_product_is_refused(db):
    user = make_user(db)
    category_id = make_category(db)
    bought = make_product(db, category_id, name="Bought")
    other = make_product(db, category_id, name="Other")
    deliver(db, place_order(db, user["_id"], [{"product_id": bought["_id"], "qty": 1}]))

    with pytest.raises(NotPurchased):
        add_review(db, user["_id"], other["_id"], 4)


def test_cancelled_order_does_not_allow_review(db):
    user = make_user(db)
    mouse = make_product(db)
    order = place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}])
    cancel_order(db, order["_id"])
    with pytest.raises(NotPurchased):
        add_review(db, user["_id"], mouse["_id"], 5)


def test_second_review_is_rejected(db):
    user = make_user(db)
    mouse = make_product(db)
    deliver(db, place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}]))

    add_review(db, user["_id"], mouse["_id"], 4)
    with pytest.raises(AlreadyReviewed):
        add_review(db, user["_id"], mouse["_id"], 1)
    assert db.reviews.count_documents({}) == 1


@pytest.mark.parametrize("rating", [0, 6, -1, 3.5, "5", True, None])
def test_review_rating_must_be_int_1_to_5(db, rating):
    user = make_user(db)
    mouse = make_product(db)
    deliver(db, place_order(db, user["_id"], [{"product_id": mouse["_id"], "qty": 1}]))
    with pytest.raises(ValueError):
        add_review(db, user["_id"], mouse["_id"], rating)
    assert db.reviews.count_documents({}) == 0


def test_review_unknown_user_or_product(db):
    user = make_user(db)
    mouse = make_product(db)
    with pytest.raises(NotFound):
        add_review(db, ObjectId(), mouse["_id"], 5)
    with pytest.raises(NotFound):
        add_review(db, user["_id"], ObjectId(), 5)