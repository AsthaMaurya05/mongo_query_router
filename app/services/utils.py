from bson import ObjectId
from bson.errors import InvalidId

from app.services.errors import NotFound


def to_object_id(value, resource_name="Resource"):
    """
    Convert an incoming id to an ObjectId, or raise NotFound.

    Only an ObjectId or a valid 24-character hex string is accepted.
    Everything else (None, numbers, junk strings) is treated as "not found".

    Why this is stricter than calling ObjectId(value) directly:
    ObjectId(None) does not fail. It silently creates a brand-new random id,
    so a missing id would turn into a confusing "not found" much later.
    """
    if isinstance(value, ObjectId):
        return value

    if isinstance(value, str):
        try:
            return ObjectId(value)
        except InvalidId:
            pass

    raise NotFound(f"{resource_name} not found.")