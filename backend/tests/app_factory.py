"""Test application factory that never touches host services."""

from fastapi import FastAPI

from app.main import create_app


class NoopHostLifecycle:
    """Disable host startup and shutdown side effects in ordinary API tests."""

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


def create_test_app() -> FastAPI:
    return create_app(host_lifecycle=NoopHostLifecycle())
