"""Exceptions raised by the service layer.

The API layer (FastAPI, Step 9) will translate these into HTTP responses:
NotFound -> 404, DuplicateEmail / OutOfStock / InvalidTransition /
UserHasOrders / AlreadyReviewed -> 409, NotPurchased -> 403, ValueError -> 422.
"""


class ServiceError(Exception):
    """Base exception for service-layer errors."""


class NotFound(ServiceError):
    """The requested resource does not exist."""


class DuplicateEmail(ServiceError):
    """A user with this email already exists."""


class OutOfStock(ServiceError):
    """There is insufficient stock to fulfill an order."""


class InvalidTransition(ServiceError):
    """The requested order-status transition is not allowed."""


class NotPurchased(ServiceError):
    """The user has not purchased the product in a delivered order."""


class AlreadyReviewed(ServiceError):
    """The user has already reviewed this product."""


class UserHasOrders(ServiceError):
    """The user cannot be deleted because they have existing orders."""