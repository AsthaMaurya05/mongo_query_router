import logging
from datetime import datetime, timezone

from pymongo import ReturnDocument, UpdateOne

from app.services.errors import InvalidTransition, NotFound, OutOfStock
from app.services.utils import to_object_id

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS = {
    "placed": {"shipped", "cancelled"},
    "shipped": {"delivered", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


def _merge_items(items):
    """
    Validate the order lines and merge repeated products.

    [A x2, A x3] becomes {A: 5}, so stock is checked against the real total.
    Without merging, two lines of 3 against stock 5 would each pass a check
    for 3 but together ask for 6.
    """
    if not isinstance(items, list) or not items:
        raise ValueError("An order must contain at least one item.")

    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each item must be a dictionary.")

        product_id = to_object_id(item.get("product_id"), "Product")
        qty = item.get("qty")

        # bool is a subclass of int in Python, so reject True and False.
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            raise ValueError("Each item quantity must be a positive integer.")

        quantities[product_id] = quantities.get(product_id, 0) + qty

    return quantities


def _restore_stock(db, pairs):
    """Add stock back for [(product_id, qty), ...] in a single round trip."""
    if not pairs:
        return

    db.products.bulk_write(
        [UpdateOne({"_id": pid}, {"$inc": {"stock": qty}}) for pid, qty in pairs],
        ordered=False,
    )


def _rollback(db, deducted):
    """
    Undo stock deductions after a failed order.

    If the undo itself fails, we must not hide the original error, so we
    log the problem and let the caller re-raise the real one.
    """
    try:
        _restore_stock(db, deducted)
    except Exception:
        logger.exception("Could not restore stock; repair by hand: %s", deducted)


def place_order(db, user_id, items):
    """
    Place an order, taking stock atomically for each product.

    For every product we run ONE conditional update:
        update where stock >= qty, then decrement stock by qty
    MongoDB checks and changes the stock in a single atomic step, so two
    customers can never both take the last unit. (Check-then-write in
    Python would let both through.)

    The same call also returns the product, so the price saved in the order
    is exactly the price at the moment the stock was taken.

    There are no multi-document transactions on a standalone server, so if
    any line fails we compensate: put back the stock already taken and
    insert no order.
    """
    user_id = to_object_id(user_id, "User")

    if db.users.find_one({"_id": user_id}, {"_id": 1}) is None:
        raise NotFound("User not found.")

    quantities = _merge_items(items)

    deducted = []      # [(product_id, qty)] already taken, needed for rollback
    order_items = []

    try:
        for product_id, qty in quantities.items():
            product = db.products.find_one_and_update(
                {"_id": product_id, "stock": {"$gte": qty}},
                {"$inc": {"stock": -qty}},
                projection={"name": 1, "price": 1},
                return_document=ReturnDocument.AFTER,
            )

            if product is None:
                # Either the product does not exist, or it has too little stock.
                existing = db.products.find_one({"_id": product_id}, {"name": 1})
                if existing is None:
                    raise NotFound(f"Product {product_id} not found.")
                raise OutOfStock(
                    f"Insufficient stock for product '{existing['name']}'."
                )

            deducted.append((product_id, qty))
            order_items.append({
                "product_id": product_id,
                "name": product["name"],      # snapshot at purchase time
                "price": product["price"],    # snapshot at purchase time
                "qty": qty,
            })

        order = {
            "user_id": user_id,
            "status": "placed",
            "created_at": datetime.now(timezone.utc),
            "items": order_items,
            "total": round(sum(i["price"] * i["qty"] for i in order_items), 2),
        }

        result = db.orders.insert_one(order)

    except Exception:
        _rollback(db, deducted)
        raise

    return db.orders.find_one({"_id": result.inserted_id})


def get_order(db, order_id):
    """Return one order or raise NotFound."""
    order_id = to_object_id(order_id, "Order")
    order = db.orders.find_one({"_id": order_id})

    if order is None:
        raise NotFound("Order not found.")

    return order


def get_orders_for_user(db, user_id, limit=10):
    """
    Return a user's newest orders first.

    Uses the (user_id, created_at descending) index: MongoDB reads entries
    that are already in order and stops after `limit`, with no sort step.
    """
    user_id = to_object_id(user_id, "User")

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer.")

    if db.users.find_one({"_id": user_id}, {"_id": 1}) is None:
        raise NotFound("User not found.")

    return list(
        db.orders.find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )


def update_order_status(db, order_id, new_status):
    """
    Apply only permitted status changes:
        placed  -> shipped or cancelled
        shipped -> delivered or cancelled

    The update filter includes the status we just read. If another request
    changed the order in between, nothing matches, so two simultaneous
    cancellations can never restore the stock twice.
    """
    order_id = to_object_id(order_id, "Order")

    if new_status not in ALLOWED_TRANSITIONS:
        raise InvalidTransition(f"Unknown order status: {new_status}")

    order = db.orders.find_one({"_id": order_id})

    if order is None:
        raise NotFound("Order not found.")

    current_status = order["status"]

    if new_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidTransition(
            f"Cannot change order from '{current_status}' to '{new_status}'."
        )

    updated = db.orders.find_one_and_update(
        {"_id": order_id, "status": current_status},
        {"$set": {"status": new_status}},
        return_document=ReturnDocument.AFTER,
    )

    if updated is None:
        raise InvalidTransition(
            "Order status changed concurrently; please retry."
        )

    if new_status == "cancelled":
        try:
            _restore_stock(
                db, [(item["product_id"], item["qty"]) for item in order["items"]]
            )
        except Exception:
            # The order is already cancelled; make the failure loud, not silent.
            logger.exception("Order %s cancelled but stock not restored", order_id)
            raise

    return updated


def cancel_order(db, order_id):
    """Cancel an order and restore its stock."""
    return update_order_status(db, order_id, "cancelled")