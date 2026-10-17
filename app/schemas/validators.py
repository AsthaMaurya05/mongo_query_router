
# app/schemas/validators.py

# 1. USERS
users_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "email", "city", "joined_at"],
        "properties": {
            "name": {
                "bsonType": "string",
                "minLength": 1
            },
            "email": {
                "bsonType": "string",
                "pattern": "^.+@.+\\..+$"
            },
            "city": {
                "bsonType": "string"
            },
            "joined_at": {
                "bsonType": "date"
            }
        }
    }
}


# 2. CATEGORIES
categories_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name"],
        "properties": {
            "name": {
                "bsonType": "string",
                "minLength": 1
            }
        }
    }
}


# 3. PRODUCTS
products_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "name", "category_id", "price", "stock", "tags"
        ],
        "properties": {
            "name": {
                "bsonType": "string",
                "minLength": 1
            },
            "category_id": {
                "bsonType": "objectId"
            },
            "price": {
                "bsonType": ["double", "int", "long", "decimal"],
                "minimum": 0
            },
            "stock": {
                "bsonType": "int",
                "minimum": 0
            },
            "tags": {
                "bsonType": "array",
                "items": {
                    "bsonType": "string"
                }
            }
        }
    }
}


# 4. ORDERS
orders_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "user_id", "status", "created_at", "items", "total"
        ],
        "properties": {
            "user_id": {
                "bsonType": "objectId"
            },
            "status": {
                "bsonType": "string",
                "enum": ["placed", "shipped", "delivered", "cancelled"]
            },
            "created_at": {
                "bsonType": "date"
            },
            "items": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": [
                        "product_id", "name", "price", "qty"
                    ],
                    "properties": {
                        "product_id": {
                            "bsonType": "objectId"
                        },
                        "name": {
                            "bsonType": "string",
                            "minLength": 1
                        },
                        "price": {
                            "bsonType": [
                                "double", "int", "long", "decimal"
                            ],
                            "minimum": 0
                        },
                        "qty": {
                            "bsonType": "int",
                            "minimum": 1
                        }
                    }
                }
            },
            "total": {
                "bsonType": ["double", "int", "long", "decimal"],
                "minimum": 0
            }
        }
    }
}


# 5. REVIEWS
reviews_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "user_id", "product_id", "rating", "created_at"
        ],
        "properties": {
            "user_id": {
                "bsonType": "objectId"
            },
            "product_id": {
                "bsonType": "objectId"
            },
            "rating": {
                "bsonType": "int",
                "minimum": 1,
                "maximum": 5
            },
            "comment": {
                "bsonType": "string"
            },
            "created_at": {
                "bsonType": "date"
            }
        }
    }
}
