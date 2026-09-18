"""Tests for job handler registration and dispatch."""

from typing import Any

import pytest

from worker.handlers import echo
from worker.registry import HandlerRegistry, UnknownJobTypeError


def test_registered_handler_can_be_looked_up() -> None:
    registry = HandlerRegistry()
    registry.register("example", echo)

    assert registry.get("example") is echo


def test_unknown_handler_raises_specific_error() -> None:
    registry = HandlerRegistry()

    with pytest.raises(
        UnknownJobTypeError,
        match="no handler registered for job type 'missing'",
    ):
        registry.get("missing")


@pytest.mark.parametrize(
    "payload",
    [None, "hello", [1, 2], {"message": "hello", "nested": {"ok": True}}],
)
def test_echo_handler_returns_input_payload(payload: Any) -> None:
    assert echo(payload) is payload


def test_registry_dispatches_payload_to_matching_handler() -> None:
    received: list[Any] = []

    def handler(payload: Any) -> dict[str, Any]:
        received.append(payload)
        return {"handled": payload}

    registry = HandlerRegistry()
    registry.register("example", handler)
    payload = {"value": 7}

    result = registry.dispatch("example", payload)

    assert received == [payload]
    assert result == {"handled": payload}
