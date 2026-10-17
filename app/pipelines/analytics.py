def revenue_by_category(start, end, limit=5):
    """
    Version A:
    Match orders -> unwind items -> lookup each product
    -> group by category -> sort -> limit -> lookup category names.

    Date range: start inclusive, end exclusive.
    Only delivered orders count as revenue.
    """
    return [
        {
            "$match": {
                "status": "delivered",
                "created_at": {"$gte": start, "$lt": end},
            }
        },
        {"$unwind": "$items"},
        {
            "$lookup": {
                "from": "products",
                "localField": "items.product_id",
                "foreignField": "_id",
                "as": "product",
            }
        },
        {"$unwind": "$product"},
        {
            "$group": {
                "_id": "$product.category_id",
                "revenue": {
                    "$sum": {
                        "$multiply": ["$items.price", "$items.qty"]
                    }
                },
            }
        },
        {"$sort": {"revenue": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "categories",
                "localField": "_id",
                "foreignField": "_id",
                "as": "category",
            }
        },
        {
            "$unwind": {
                "path": "$category",
                "preserveNullAndEmptyArrays": True,
            }
        },
        {
            "$project": {
                "_id": 0,
                "category_id": "$_id",
                "category": "$category.name",
                "revenue": {"$round": ["$revenue", 2]},
            }
        },
    ]


def revenue_by_category_v2(start, end, limit=5):
    """
    Version B:
    Group item revenue by product first, then lookup products.
    This reduces product lookups when many order items belong
    to the same product.
    """
    return [
        {
            "$match": {
                "status": "delivered",
                "created_at": {"$gte": start, "$lt": end},
            }
        },
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.product_id",
                "revenue": {
                    "$sum": {
                        "$multiply": ["$items.price", "$items.qty"]
                    }
                },
            }
        },
        {
            "$lookup": {
                "from": "products",
                "localField": "_id",
                "foreignField": "_id",
                "as": "product",
            }
        },
        {"$unwind": "$product"},
        {
            "$group": {
                "_id": "$product.category_id",
                "revenue": {"$sum": "$revenue"},
            }
        },
        {"$sort": {"revenue": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "categories",
                "localField": "_id",
                "foreignField": "_id",
                "as": "category",
            }
        },
        {
            "$unwind": {
                "path": "$category",
                "preserveNullAndEmptyArrays": True,
            }
        },
        {
            "$project": {
                "_id": 0,
                "category_id": "$_id",
                "category": "$category.name",
                "revenue": {"$round": ["$revenue", 2]},
            }
        },
    ]


def top_customers(start, end, limit=10):
    """
    Sum order totals per user.
    Sort and limit before looking up user details.
    """
    return [
        {
            "$match": {
                "status": "delivered",
                "created_at": {"$gte": start, "$lt": end},
            }
        },
        {
            "$group": {
                "_id": "$user_id",
                "total_spend": {"$sum": "$total"},
                "order_count": {"$sum": 1},
            }
        },
        {"$sort": {"total_spend": -1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user",
            }
        },
        {
            "$unwind": {
                "path": "$user",
                "preserveNullAndEmptyArrays": True,
            }
        },
        {
            "$project": {
                "_id": 0,
                "user_id": "$_id",
                "email": "$user.email",
                "total_spend": {"$round": ["$total_spend", 2]},
                "order_count": 1,
            }
        },
    ]


def monthly_revenue_trend(start, end):
    """
    Monthly delivered revenue, order count and average order value.
    Requires MongoDB 5.0+ for $dateTrunc.
    """
    return [
        {
            "$match": {
                "status": "delivered",
                "created_at": {"$gte": start, "$lt": end},
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": "$created_at",
                        "unit": "month",
                    }
                },
                "revenue": {"$sum": "$total"},
                "order_count": {"$sum": 1},
                "average_order_value": {"$avg": "$total"},
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "month": {
                    "$dateToString": {
                        "format": "%Y-%m",
                        "date": "$_id",
                    }
                },
                "revenue": {"$round": ["$revenue", 2]},
                "order_count": 1,
                "average_order_value": {
                    "$round": ["$average_order_value", 2]
                },
            }
        },
    ]



def order_status_summary(start, end):
    """
    Count orders and sum their total value by status.
    Includes all statuses, not just delivered orders.
    Date range: start inclusive, end exclusive.
    """
    return [
        {
            "$match": {
                "created_at": {"$gte": start, "$lt": end}
            }
        },
        {
            "$group": {
                "_id": "$status",
                "order_count": {"$sum": 1},
                "total_value": {"$sum": "$total"},
            }
        },
        {
            "$sort": {
                "order_count": -1,
                "_id": 1,
            }
        },
        {
            "$project": {
                "_id": 0,
                "status": "$_id",
                "order_count": 1,
                "total_value": {"$round": ["$total_value", 2]},
            }
        },
    ]

def low_stock_alert(threshold=10):
    """
    Find products with stock strictly below the threshold.
    Include the category name and sort by lowest stock first.
    """
    return [
        {
            "$match": {
                "stock": {"$lt": threshold}
            }
        },
        {
            "$lookup": {
                "from": "categories",
                "localField": "category_id",
                "foreignField": "_id",
                "as": "category",
            }
        },
        {
            "$unwind": "$category"
        },
        {
            "$sort": {
                "stock": 1,
                "name": 1,
            }
        },
        {
            "$project": {
                "_id": 0,
                "name": 1,
                "stock": 1,
                "category": "$category.name",
            }
        },
    ]



def product_ratings(min_reviews=10, limit=10):
    """
    Rank products by average review rating.
    Only include products with at least min_reviews reviews.
    """
    return [
        {
            "$group": {
                "_id": "$product_id",
                "average_rating": {"$avg": "$rating"},
                "review_count": {"$sum": 1},
            }
        },
        {
            "$match": {
                "review_count": {"$gte": min_reviews}
            }
        },
        {
            "$sort": {
                "average_rating": -1,
                "review_count": -1,
                "_id": 1,
            }
        },
        {
            "$limit": limit
        },
        {
            "$lookup": {
                "from": "products",
                "localField": "_id",
                "foreignField": "_id",
                "as": "product",
            }
        },
        {
            "$unwind": "$product"
        },
        {
            "$project": {
                "_id": 0,
                "product_id": "$_id",
                "product_name": "$product.name",
                "average_rating": {"$round": ["$average_rating", 2]},
                "review_count": 1,
            }
        },
    ]


def price_band_distribution():
    """
    Count products in predefined price bands.
    Prices outside the boundaries go into the default bucket.
    """
    return [
        {
            "$bucket": {
                "groupBy": "$price",
                "boundaries": [0, 500, 1000, 2500, 5000, 10000, 20000],
                "default": "other",
                "output": {
                    "product_count": {"$sum": 1},
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "price_band": "$_id",
                "product_count": 1,
            }
        },
        {
            "$sort": {
                "price_band": 1,
            }
        },
    ]


def dashboard_summary(start, end):
    """
    Summarize delivered-order metrics, top products, and order sizes
    for the selected date range.
    """
    return [
        {
            "$match": {
                "status": "delivered",
                "created_at": {
                    "$gte": start,
                    "$lt": end,
                },
            }
        },
        {
            "$facet": {
                "totals": [
                    {
                        "$group": {
                            "_id": None,
                            "revenue": {"$sum": "$total"},
                            "order_count": {"$sum": 1},
                            "average_order_value": {"$avg": "$total"},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "revenue": {"$round": ["$revenue", 2]},
                            "order_count": 1,
                            "average_order_value": {
                                "$round": ["$average_order_value", 2]
                            },
                        }
                    },
                ],
                "top_products": [
                    {"$unwind": "$items"},
                    {
                        "$group": {
                            "_id": "$items.product_id",
                            "product_name": {"$first": "$items.name"},
                            "revenue": {
                                "$sum": {
                                    "$multiply": [
                                        "$items.price",
                                        "$items.qty",
                                    ]
                                }
                            },
                        }
                    },
                    {"$sort": {"revenue": -1, "_id": 1}},
                    {"$limit": 5},
                    {
                        "$project": {
                            "_id": 0,
                            "product_id": "$_id",
                            "product_name": 1,
                            "revenue": {"$round": ["$revenue", 2]},
                        }
                    },
                ],
                "order_size": [
                    {
                        "$bucket": {
                            "groupBy": "$total",
                            "boundaries": [
                                0, 500, 1000, 2500, 5000,
                                10000, 20000,
                            ],
                            "default": "other",
                            "output": {
                                "order_count": {"$sum": 1},
                            },
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "price_band": "$_id",
                            "order_count": 1,
                        }
                    },
                    {"$sort": {"price_band": 1}},
                ],
            }
        },
        {
            "$project": {
                "_id": 0,
                "totals": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$totals", 0]},
                        {
                            "revenue": 0,
                            "order_count": 0,
                            "average_order_value": 0,
                        },
                    ]
                },
                "top_products": 1,
                "order_size": 1,
            }
        },
    ]
