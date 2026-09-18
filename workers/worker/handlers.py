"""Built-in job handlers and default registry construction."""

from __future__ import annotations

from typing import Any

from worker.registry import HandlerRegistry


def echo(payload: Any) -> Any:
    """Return the supplied payload unchanged."""
    return payload


def create_default_registry() -> HandlerRegistry:
    """Create the registry used by the command-line worker."""
    registry = HandlerRegistry()
    registry.register("echo", echo)
    return registry
