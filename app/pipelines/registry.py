from datetime import date, datetime, time, timezone


from app.pipelines.analytics import (
    revenue_by_category,
    revenue_by_category_v2,
    top_customers,
    monthly_revenue_trend,
    order_status_summary,
    low_stock_alert,
    product_ratings,
    price_band_distribution, 
    dashboard_summary,
)

PIPELINE_REGISTRY = {
    "revenue_by_category": {
        "builder": revenue_by_category_v2,
        "collection": "orders",
        "description": "Revenue per product category in a date range",
        "params": {
            "start": {"type": "date", "required": True},
            "end": {"type": "date", "required": True},
            "limit": {
                "type": "int",
                "min": 1,
                "max": 20,
                "default": 5,
            },
        },
    },
    "revenue_by_category_naive": {
        "builder": revenue_by_category,
        "collection": "orders",
        "description": "Naive category revenue aggregation for benchmarking",
        # Benchmark only. It takes about 10 s on 50,000 orders, longer than
        # the 5 s maxTimeMS limit, so the router and agent must never pick it.
        "public": False,
        "params": {
            "start": {"type": "date", "required": True},
            "end": {"type": "date", "required": True},
            "limit": {
                "type": "int",
                "min": 1,
                "max": 20,
                "default": 5,
            },
        },
    },
    "top_customers": {
        "builder": top_customers,
        "collection": "orders",
        "description": "Top customers by delivered-order spend",
        "params": {
            "start": {"type": "date", "required": True},
            "end": {"type": "date", "required": True},
            "limit": {
                "type": "int",
                "min": 1,
                "max": 100,
                "default": 10,
            },
        },
    },
    "monthly_revenue_trend": {
        "builder": monthly_revenue_trend,
        "collection": "orders",
        "description": (
            "Monthly delivered revenue, order count and average order value"
        ),
        "params": {
            "start": {"type": "date", "required": True},
            "end": {"type": "date", "required": True},
        },
    },
    "order_status_summary": {
        "builder": order_status_summary,
        "collection": "orders",
        "description": "Order counts and total value grouped by status",
        "params": {
            "start": {"type": "date", "required": True},
            "end": {"type": "date", "required": True},
        },
    },
    "low_stock_alert": {
        "builder": low_stock_alert,
        "collection": "products",
        "description": "Find products with stock below a specified threshold",
        "params": {
            "threshold": {
                "type": "int",
                "required": False,
                "min": 1,
                "max": 1000,
                "default": 10,
            },
        },
    },
    "product_ratings": {
        "builder": product_ratings,
        "collection": "reviews",
        "description": "Rank products by average rating with a minimum review count",
        "params": {
            "min_reviews": {
                "type": "int",
                "required": False,
                "min": 1,
                "max": 1000,
                "default": 10,
            },
            "limit": {
                "type": "int",
                "required": False,
                "min": 1,
                "max": 100,
                "default": 10,
            },
        },
    },
    "price_band_distribution": {
        "builder": price_band_distribution,
        "collection": "products",
        "description": "Count products grouped into predefined price bands",
        "params": {},
    },
    "dashboard_summary": {
        "builder": dashboard_summary,
        "collection": "orders",
        "description": "Summarize delivered-order metrics, top products, and order sizes",
        "params": {
            "start": {
                "type": "date",
                "required": True,
            },
            "end": {
                "type": "date",
                "required": True,
            },
        },
    },
}


def list_public_pipelines():
    """
    Pipelines the AI router and agent may choose from.
    Anything marked "public": False (benchmark-only) is hidden from them.
    """
    return {
        name: config
        for name, config in PIPELINE_REGISTRY.items()
        if config.get("public", True)
    }


def _parse_datetime(value, parameter_name):
    """Parse a date or datetime and normalize it to UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        try:
            # Also accepts ISO strings ending in Z on supported Python versions.
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(
                f"{parameter_name} must be a valid ISO date/datetime string"
            ) from error
    else:
        raise ValueError(
            f"{parameter_name} must be a date, datetime, or ISO string"
        )

    # Treat naive values as UTC; convert aware values to UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    return parsed


def validate_params(name, params):
    """Validate pipeline arguments using the registry's parameter schema."""
    if name not in PIPELINE_REGISTRY:
        raise ValueError(f"Unknown pipeline: {name}")

    if not isinstance(params, dict):
        raise ValueError("params must be a dictionary")

    config = PIPELINE_REGISTRY[name]
    spec = config["params"]

    unknown = set(params) - set(spec)
    if unknown:
        raise ValueError(f"Unexpected parameter(s): {sorted(unknown)}")

    result = {}

    for param_name, rules in spec.items():
        if param_name not in params:
            if rules.get("required", False):
                raise ValueError(f"{param_name} is required")

            if "default" in rules:
                result[param_name] = rules["default"]

            continue

        value = params[param_name]
        param_type = rules["type"]

        if param_type == "date":
            result[param_name] = _parse_datetime(value, param_name)

        elif param_type == "int":
            # bool is a subclass of int, so reject True and False.
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{param_name} must be an integer")

            minimum = rules.get("min")
            maximum = rules.get("max")

            if minimum is not None and value < minimum:
                raise ValueError(
                    f"{param_name} must be at least {minimum}"
                )

            if maximum is not None and value > maximum:
                raise ValueError(
                    f"{param_name} must be at most {maximum}"
                )

            result[param_name] = value

        else:
            raise ValueError(
                f"Unsupported parameter type '{param_type}' "
                f"for {param_name}"
            )

    if "start" in result and "end" in result:
        if result["start"] >= result["end"]:
            raise ValueError("start must be earlier than end")

    return result


def run_pipeline(db, name, params):
    """Validate arguments, build the pipeline, and execute it."""
    validated = validate_params(name, params)
    config = PIPELINE_REGISTRY[name]
    pipeline = config["builder"](**validated)

    return list(
        db[config["collection"]].aggregate(
            pipeline,
            maxTimeMS=5000,
        )
    )