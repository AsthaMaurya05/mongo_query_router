#tests/test_router.py
import json
from types import SimpleNamespace

import pytest

from app.ai.router import (
    QueryRouter,
    RouterOutputError,
    RouterUnavailableError,
)


class FakeGroqClient:
    """Small fake for the Groq chat-completions interface."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)

        if not self.responses:
            raise AssertionError("No fake response configured.")

        response = self.responses.pop(0)

        if isinstance(response, Exception):
            raise response

        message = SimpleNamespace(content=response)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


def test_routes_to_public_pipeline_and_validates_params():
    client = FakeGroqClient([
        json.dumps({
            "pipeline": "revenue_by_category",
            "params": {
                "start": "2026-09-01",
                "end": "2026-10-01",
                "limit": 3,
            },
        })
    ])

    router = QueryRouter(client=client)
    result = router.route("Top 3 categories by revenue last month")

    assert result["pipeline"] == "revenue_by_category"
    assert result["params"]["limit"] == 3
    assert result["params"]["start"].isoformat().startswith("2026-09-01")
    assert result["params"]["end"].isoformat().startswith("2026-10-01")
    assert len(client.calls) == 1
    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_non_analytics_question_returns_no_pipeline():
    client = FakeGroqClient([
        '{"pipeline": null, "params": {}}'
    ])

    result = QueryRouter(client=client).route(
        "What is the weather today?"
    )

    assert result == {"pipeline": None, "params": {}}


def test_unknown_pipeline_is_rejected_then_retried():
    client = FakeGroqClient([
        '{"pipeline": "delete_everything", "params": {}}',
        '{"pipeline": "price_band_distribution", "params": {}}',
    ])

    result = QueryRouter(client=client).route(
        "Show the product price bands"
    )

    assert result["pipeline"] == "price_band_distribution"
    assert len(client.calls) == 2
    assert "not in the public menu" in client.calls[1]["messages"][-1]["content"]


def test_invalid_params_are_rejected_then_retried():
    client = FakeGroqClient([
        json.dumps({
            "pipeline": "revenue_by_category",
            "params": {
                "start": "2026-09-01",
                "end": "2026-10-01",
                "limit": 500,
            },
        }),
        '{"pipeline": "price_band_distribution", "params": {}}',
    ])

    result = QueryRouter(client=client).route(
        "Show product price bands"
    )

    assert result["pipeline"] == "price_band_distribution"
    assert len(client.calls) == 2


def test_extra_json_key_is_rejected():
    client = FakeGroqClient([
        '{"pipeline": "price_band_distribution", "params": {}, "query": "oops"}',
        '{"pipeline": "price_band_distribution", "params": {}, "query": "oops"}',
    ])

    with pytest.raises(RouterOutputError):
        QueryRouter(client=client).route("Show product price bands")

    assert len(client.calls) == 2


def test_invalid_json_is_retried_once():
    client = FakeGroqClient([
        "This is not JSON",
        "Still not JSON",
    ])

    with pytest.raises(RouterOutputError):
        QueryRouter(client=client).route("Show product price bands")

    assert len(client.calls) == 2


def test_private_benchmark_pipeline_cannot_be_selected():
    client = FakeGroqClient([
        '{"pipeline": "revenue_by_category_naive", '
        '"params": {"start": "2026-09-01", "end": "2026-10-01"}}',
        '{"pipeline": "price_band_distribution", "params": {}}',
    ])

    result = QueryRouter(client=client).route(
        "Show product price bands"
    )

    assert result["pipeline"] == "price_band_distribution"


def test_api_error_has_clean_message():
    client = FakeGroqClient([
        RuntimeError("simulated network failure")
    ])

    with pytest.raises(RouterUnavailableError, match="Groq API request failed"):
        QueryRouter(client=client).route("Show product price bands")


def test_empty_question_is_rejected_without_api_call():
    client = FakeGroqClient([])
    router = QueryRouter(client=client)

    with pytest.raises(ValueError, match="non-empty"):
        router.route("   ")

    assert len(client.calls) == 0
