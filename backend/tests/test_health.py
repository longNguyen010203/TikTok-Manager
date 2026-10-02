"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from tests.app_factory import create_test_app


def test_health() -> None:
    with TestClient(create_test_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
