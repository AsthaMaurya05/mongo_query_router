
"""Hand-labelled benchmark for natural-language analytics routing."""

ROUTER_QUESTIONS = [
    # 1–5: Revenue by category
    {
        "question": "Show revenue by category from September 1 to October 1, 2026",
        "expected_pipeline": "revenue_by_category",
        "expected_params": {
            "start": "2026-09-01",
            "end": "2026-10-01",
            "limit": 5,
        },
    },
    {
        "question": "Which are the top 3 categories by revenue between January 1 and April 1, 2026?",
        "expected_pipeline": "revenue_by_category",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-04-01",
            "limit": 3,
        },
    },
    {
        "question": "Compare category revenue for the first half of 2026",
        "expected_pipeline": "revenue_by_category",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-07-01",
            "limit": 5,
        },
    },
    {
        "question": "Give me the top 10 product categories by revenue from July 1 to August 1, 2026",
        "expected_pipeline": "revenue_by_category",
        "expected_params": {
            "start": "2026-07-01",
            "end": "2026-08-01",
            "limit": 10,
        },
    },
    {
        "question": "Show category revenue from March 1 to April 1, 2026, limited to 1 category",
        "expected_pipeline": "revenue_by_category",
        "expected_params": {
            "start": "2026-03-01",
            "end": "2026-04-01",
            "limit": 1,
        },
    },

    # 6–9: Top customers
    {
        "question": "Show the top customers by delivered-order spend from January 1 to February 1, 2026",
        "expected_pipeline": "top_customers",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-02-01",
            "limit": 10,
        },
    },
    {
        "question": "Who are the top 5 customers by spending between April 1 and May 1, 2026?",
        "expected_pipeline": "top_customers",
        "expected_params": {
            "start": "2026-04-01",
            "end": "2026-05-01",
            "limit": 5,
        },
    },
    {
        "question": "Rank the top 20 customers by delivered-order spending from January 1 to January 31, 2026",
        "expected_pipeline": "top_customers",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-02-01",
            "limit": 20,
        },
    },
    {
        "question": "List the top 2 highest-spending customers between September 1 and October 1, 2026",
        "expected_pipeline": "top_customers",
        "expected_params": {
            "start": "2026-09-01",
            "end": "2026-10-01",
            "limit": 2,
        },
    },

    # 10–13: Monthly revenue trend
    {
        "question": "Show the monthly revenue trend for 2026",
        "expected_pipeline": "monthly_revenue_trend",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2027-01-01",
        },
    },
    {
        "question": "Display monthly revenue, order count, and average order value from January 1 to July 1, 2026",
        "expected_pipeline": "monthly_revenue_trend",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-07-01",
        },
    },
    {
        "question": "How did monthly revenue change between April 1 and October 1, 2026?",
        "expected_pipeline": "monthly_revenue_trend",
        "expected_params": {
            "start": "2026-04-01",
            "end": "2026-10-01",
        },
    },
    {
        "question": "Give me the monthly sales trend for 2025",
        "expected_pipeline": "monthly_revenue_trend",
        "expected_params": {
            "start": "2025-01-01",
            "end": "2026-01-01",
        },
    },

    # 14–16: Order status summary
    {
        "question": "Summarize order counts and values by status from January 1 to February 1, 2026",
        "expected_pipeline": "order_status_summary",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-02-01",
        },
    },
    {
        "question": "How many orders are pending, delivered, or cancelled between June 1 and July 1, 2026?",
        "expected_pipeline": "order_status_summary",
        "expected_params": {
            "start": "2026-06-01",
            "end": "2026-07-01",
        },
    },
    {
        "question": "Break down order statuses for the period October 1 to November 1, 2026",
        "expected_pipeline": "order_status_summary",
        "expected_params": {
            "start": "2026-10-01",
            "end": "2026-11-01",
        },
    },

    # 17–19: Low-stock alerts
    {
        "question": "Which products have low stock?",
        "expected_pipeline": "low_stock_alert",
        "expected_params": {"threshold": 10},
    },
    {
        "question": "Find products with fewer than 5 units in stock",
        "expected_pipeline": "low_stock_alert",
        "expected_params": {"threshold": 5},
    },
    {
        "question": "Alert me about products whose stock is below 25",
        "expected_pipeline": "low_stock_alert",
        "expected_params": {"threshold": 25},
    },

    # 20–22: Product ratings
    {
        "question": "Rank products by average rating",
        "expected_pipeline": "product_ratings",
        "expected_params": {
            "min_reviews": 10,
            "limit": 10,
        },
    },
    {
        "question": "Show the top 5 products by average rating with at least 20 reviews",
        "expected_pipeline": "product_ratings",
        "expected_params": {
            "min_reviews": 20,
            "limit": 5,
        },
    },
    {
        "question": "List the top 15 highest-rated products that have at least 50 reviews",
        "expected_pipeline": "product_ratings",
        "expected_params": {
            "min_reviews": 50,
            "limit": 15,
        },
    },

    # 23–24: Price-band distribution
    {
        "question": "Show the distribution of product prices",
        "expected_pipeline": "price_band_distribution",
        "expected_params": {},
    },
    {
        "question": "How many products fall into each predefined price range?",
        "expected_pipeline": "price_band_distribution",
        "expected_params": {},
    },

    # 25–27: Dashboard summary
    {
        "question": "Give me a dashboard summary from January 1 to February 1, 2026",
        "expected_pipeline": "dashboard_summary",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-02-01",
        },
    },
    {
        "question": "Summarize delivered-order metrics, top products, and order sizes for the first half of 2026",
        "expected_pipeline": "dashboard_summary",
        "expected_params": {
            "start": "2026-01-01",
            "end": "2026-07-01",
        },
    },
    {
        "question": "Show my shop analytics dashboard for September 2026",
        "expected_pipeline": "dashboard_summary",
        "expected_params": {
            "start": "2026-09-01",
            "end": "2026-10-01",
        },
    },

    # 28–30: Unsupported questions
    {
        "question": "What is the weather in Delhi today?",
        "expected_pipeline": None,
        "expected_params": {},
    },
    {
        "question": "Write a poem about shopping",
        "expected_pipeline": None,
        "expected_params": {},
    },
    {
        "question": "Explain how a neural network works",
        "expected_pipeline": None,
        "expected_params": {},
    },
]
