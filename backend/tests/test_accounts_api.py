"""API tests for account CRUD operations."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.main import create_app


@pytest.fixture
def api_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "api-test.db")
    )
    test_engine = create_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    init_db(test_engine)

    application: FastAPI = create_app()

    def override_get_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as client:
        yield client

    application.dependency_overrides.clear()
    test_engine.dispose()


def _account_payload(index: int, status: str = "active") -> dict[str, str]:
    return {
        "name": f"Account {index}",
        "username": f"creator{index}",
        "platform": "tiktok",
        "status": status,
        "notes": f"Notes {index}",
    }


def test_account_crud(api_client: TestClient) -> None:
    create_response = api_client.post("/accounts", json=_account_payload(1))
    assert create_response.status_code == 201
    created = create_response.json()
    account_id = created["id"]
    assert created["username"] == "creator1"
    assert created["created_at"]
    assert created["updated_at"]

    get_response = api_client.get(f"/accounts/{account_id}")
    assert get_response.status_code == 200
    assert get_response.json() == created

    update_response = api_client.patch(
        f"/accounts/{account_id}", json={"name": "Updated Account", "notes": None}
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Updated Account"
    assert updated["notes"] is None
    assert updated["username"] == "creator1"

    delete_response = api_client.delete(f"/accounts/{account_id}")
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    assert api_client.get(f"/accounts/{account_id}").status_code == 404


def test_list_accounts_supports_pagination_and_status_filtering(
    api_client: TestClient,
) -> None:
    for index, account_status in enumerate(
        ["active", "inactive", "active", "active"], start=1
    ):
        response = api_client.post(
            "/accounts", json=_account_payload(index, account_status)
        )
        assert response.status_code == 201

    page_response = api_client.get("/accounts?page=2&page_size=2")
    assert page_response.status_code == 200
    page = page_response.json()
    assert page["total"] == 4
    assert page["page"] == 2
    assert page["page_size"] == 2
    assert [item["username"] for item in page["items"]] == [
        "creator3",
        "creator4",
    ]

    filtered_response = api_client.get("/accounts?status=active&page_size=2")
    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert filtered["total"] == 3
    assert [item["status"] for item in filtered["items"]] == ["active", "active"]


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_account_returns_404(api_client: TestClient, method: str) -> None:
    request = getattr(api_client, method)
    kwargs = {"json": {"name": "Updated"}} if method == "patch" else {}

    response = request("/accounts/999", **kwargs)

    assert response.status_code == 404
    assert response.json() == {"detail": "Account not found"}


def test_account_payloads_are_validated(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/accounts",
        json={"name": "", "username": "creator", "platform": "tiktok"},
    )
    assert create_response.status_code == 422

    created = api_client.post("/accounts", json=_account_payload(1)).json()
    patch_response = api_client.patch(
        f"/accounts/{created['id']}", json={"status": None}
    )
    assert patch_response.status_code == 422

    unknown_field_response = api_client.patch(
        f"/accounts/{created['id']}", json={"unknown": "value"}
    )
    assert unknown_field_response.status_code == 422
