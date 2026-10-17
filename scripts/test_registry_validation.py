from datetime import datetime, timezone

from app.pipelines.analytics import (
    revenue_by_category,
    revenue_by_category_v2,
)
from app.pipelines.registry import (
    PIPELINE_REGISTRY,
    list_public_pipelines,
    validate_params,
)


def main():
    params = {
        "start": "2026-09-01",
        "end": "2026-10-01",
    }

    validated = validate_params("revenue_by_category", params)

    assert validated["start"] == datetime(
        2026, 9, 1, tzinfo=timezone.utc
    )
    assert validated["end"] == datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )
    assert validated["limit"] == 5

    # The public pipeline must be the optimized Version B, and the slow
    # Version A must stay available for benchmarking but hidden from the AI.
    assert PIPELINE_REGISTRY["revenue_by_category"]["builder"] is revenue_by_category_v2
    assert PIPELINE_REGISTRY["revenue_by_category_naive"]["builder"] is revenue_by_category
    public = list_public_pipelines()
    assert "revenue_by_category" in public
    assert "revenue_by_category_naive" not in public
    print("PASS: public pipeline is version B; naive version hidden from the AI")

    # An aware datetime and a naive datetime should be normalized safely.
    mixed_dates = validate_params(
        "monthly_revenue_trend",
        {
            "start": datetime(2026, 9, 1),
            "end": datetime(
                2026, 10, 1, tzinfo=timezone.utc
            ),
        },
    )
    assert mixed_dates["start"].tzinfo is not None
    assert mixed_dates["end"].tzinfo is not None

    # Invalid inputs must be rejected.
    invalid_cases = [
        (
            "missing required date",
            "monthly_revenue_trend",
            {"start": "2026-09-01"},
        ),
        (
            "invalid date string",
            "monthly_revenue_trend",
            {"start": "not-a-date", "end": "2026-10-01"},
        ),
        (
            "start after end",
            "monthly_revenue_trend",
            {"start": "2026-10-01", "end": "2026-09-01"},
        ),
        (
            "limit too high",
            "revenue_by_category",
            {
                "start": "2026-09-01",
                "end": "2026-10-01",
                "limit": 21,
            },
        ),
        (
            "boolean limit",
            "revenue_by_category",
            {
                "start": "2026-09-01",
                "end": "2026-10-01",
                "limit": True,
            },
        ),
        (
            "unexpected parameter",
            "monthly_revenue_trend",
            {
                "start": "2026-09-01",
                "end": "2026-10-01",
                "limit": 5,
            },
        ),
        (
            "unknown pipeline name",
            "drop_everything",
            {"start": "2026-09-01", "end": "2026-10-01"},
        ),
        (
            "limit below minimum",
            "revenue_by_category",
            {"start": "2026-09-01", "end": "2026-10-01", "limit": 0},
        ),
        (
            "limit as string",
            "revenue_by_category",
            {"start": "2026-09-01", "end": "2026-10-01", "limit": "5"},
        ),
        (
            "limit as float",
            "revenue_by_category",
            {"start": "2026-09-01", "end": "2026-10-01", "limit": 5.0},
        ),
        (
            "start equals end",
            "monthly_revenue_trend",
            {"start": "2026-09-01", "end": "2026-09-01"},
        ),
        (
            "params not a dictionary",
            "monthly_revenue_trend",
            "2026-09-01",
        ),
    ]

    for label, name, bad_params in invalid_cases:
        try:
            validate_params(name, bad_params)
        except ValueError:
            print(f"PASS: {label}")
        else:
            raise AssertionError(f"Expected validation failure: {label}")

    print("\nPASS: ISO date parsing and UTC normalization")
    print("PASS: default limit and registry configuration")
    print("All registry validation checks passed!")


if __name__ == "__main__":
    main()