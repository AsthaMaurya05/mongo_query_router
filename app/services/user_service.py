import re
from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.services.errors import DuplicateEmail, NotFound, UserHasOrders
from app.services.utils import to_object_id

# Same rule as the users validator in app/schemas/validators.py. Checking it
# here gives a clear ValueError instead of a raw database WriteError.
EMAIL_PATTERN = re.compile(r"^.+@.+\..+$")


def create_user(db, name, email, city):
    """
    Create a user.

    Emails are stored lowercase, so "A@x.com" and "a@x.com" are the same
    account. The unique index on email is what actually prevents duplicates,
    even if two requests arrive at the same moment.
    """
    name = name.strip() if isinstance(name, str) else name
    email = email.strip().lower() if isinstance(email, str) else email
    city = city.strip() if isinstance(city, str) else city

    if not isinstance(name, str) or not name:
        raise ValueError("Name must be a non-empty string.")

    if not isinstance(email, str) or not EMAIL_PATTERN.match(email):
        raise ValueError("Email must look like name@domain.com.")

    if not isinstance(city, str) or not city:
        raise ValueError("City must be a non-empty string.")

    user = {
        "name": name,
        "email": email,
        "city": city,
        "joined_at": datetime.now(timezone.utc),
    }

    try:
        result = db.users.insert_one(user)
    except DuplicateKeyError as error:
        raise DuplicateEmail(
            f"A user with email '{email}' already exists."
        ) from error

    return db.users.find_one({"_id": result.inserted_id})


def update_user_city(db, user_id, city):
    """
    Update a user's city and return the updated document.

    find_one_and_update changes and returns the document in one operation,
    so there is no gap between "update" and "read it back".
    Raises NotFound if the user does not exist.
    """
    if not isinstance(city, str) or not city.strip():
        raise ValueError("City must be a non-empty string.")

    user_id = to_object_id(user_id, "User")

    updated = db.users.find_one_and_update(
        {"_id": user_id},
        {"$set": {"city": city.strip()}},
        return_document=ReturnDocument.AFTER,
    )

    if updated is None:
        raise NotFound("User not found.")

    return updated


def delete_user(db, user_id):
    """
    Delete a user only if they have no orders.

    MongoDB has no foreign keys, so this check is our referential integrity.
    It also protects reviews: a review can only exist for a user who has a
    delivered order, so "no orders" implies "no reviews".

    Returns True on success.
    Raises NotFound if the user does not exist, UserHasOrders if they have orders.

    Known limit: an order placed between the check and the delete would
    slip through. Closing that gap needs a transaction (replica set).
    """
    user_id = to_object_id(user_id, "User")

    if db.users.find_one({"_id": user_id}, {"_id": 1}) is None:
        raise NotFound("User not found.")

    # Uses the (user_id, created_at) index; we only need to know if one exists.
    if db.orders.find_one({"user_id": user_id}, {"_id": 1}) is not None:
        raise UserHasOrders(
            "Cannot delete this user because they have existing orders."
        )

    db.users.delete_one({"_id": user_id})
    return True