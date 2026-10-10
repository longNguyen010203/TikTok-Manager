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
from app.routers.accounts import get_account_secret_provider
from app.services.account_secrets import AccountSecretProvider
from app.services.network_credentials import MasterKeyManager
from tests.app_factory import create_test_app


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

    application: FastAPI = create_test_app()
    secret_provider = AccountSecretProvider(
        MasterKeyManager(tmp_path / "config" / "credentials.key")
    )

    def override_get_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_account_secret_provider] = lambda: secret_provider
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
        "creator2",
        "creator1",
    ]

    filtered_response = api_client.get("/accounts?status=active&page_size=2")
    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert filtered["total"] == 3
    assert [item["status"] for item in filtered["items"]] == ["active", "active"]


def test_registry_fields_search_filters_metrics_and_tags(api_client: TestClient) -> None:
    created = api_client.post(
        "/accounts",
        json={
            "display_name": "Travel Creator",
            "username": "@TravelCreator",
            "email": " Creator@Example.COM ",
            "phone": "+12025550123",
            "status": "pending",
            "registration_state": "pending",
            "health_status": "healthy",
            "status_reason": "Awaiting operator review",
            "niche": "Travel",
            "notes": "Registry test",
            "tags": [" Priority ", "priority", "SEA"],
            "follower_count": 0,
            "following_count": 12,
            "likes_count": 34,
            "video_count": 2,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == body["display_name"] == "Travel Creator"
    assert body["username"] == "travelcreator"
    assert body["email"] == "creator@example.com"
    assert body["tags"] == ["priority", "sea"]
    assert body["health_status"] == "healthy"
    assert body["secret_present"] is False
    assert body["secret_types"] == []

    for path in (
        "/accounts?query=TravelCreator",
        "/accounts?niche=travel",
        "/accounts?tag=SEA",
        "/accounts?status=pending",
    ):
        result = api_client.get(path)
        assert result.status_code == 200
        assert result.json()["total"] == 1

    updated = api_client.patch(
        f"/accounts/{body['id']}",
        json={"display_name": "Updated Creator"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == updated.json()["display_name"] == "Updated Creator"


def test_metrics_are_non_negative(api_client: TestClient) -> None:
    response = api_client.post(
        "/accounts", json={"display_name": "Metrics", "follower_count": -1}
    )
    assert response.status_code == 422


def test_account_secrets_are_write_only_encrypted_and_replaceable(
    api_client: TestClient, tmp_path: Path
) -> None:
    account = api_client.post("/accounts", json={"display_name": "Secret Account"}).json()
    plaintext = "never-store-this-plaintext-value"
    written = api_client.put(
        f"/accounts/{account['id']}/secrets/account_password",
        json={"value": plaintext},
    )
    assert written.status_code == 200
    assert written.json()["present"] is True
    assert plaintext not in written.text

    detail = api_client.get(f"/accounts/{account['id']}")
    assert detail.json()["secret_present"] is True
    assert detail.json()["secret_types"] == ["account_password"]
    assert plaintext not in detail.text
    assert plaintext.encode() not in (tmp_path / "api-test.db").read_bytes()

    replacement = "replacement-secret-value"
    replaced = api_client.put(
        f"/accounts/{account['id']}/secrets/account_password",
        json={"value": replacement},
    )
    assert replaced.status_code == 200
    assert replacement not in replaced.text
    assert replacement.encode() not in (tmp_path / "api-test.db").read_bytes()
    assert len(api_client.get(f"/accounts/{account['id']}/secrets").json()) == 1

    deleted = api_client.delete(
        f"/accounts/{account['id']}/secrets/account_password"
    )
    assert deleted.status_code == 204
    assert api_client.get(f"/accounts/{account['id']}").json()["secret_present"] is False


def test_secret_validation_never_echoes_plaintext(api_client: TestClient) -> None:
    account = api_client.post("/accounts", json={"display_name": "Safe Errors"}).json()
    plaintext = "value-that-must-not-leak"
    response = api_client.put(
        f"/accounts/{account['id']}/secrets/not-allowed",
        json={"value": plaintext},
    )
    assert response.status_code == 422
    assert plaintext not in response.text


def test_missing_secret_master_key_fails_closed_without_leaking_value(
    api_client: TestClient, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    account = api_client.post("/accounts", json={"display_name": "Missing Key"}).json()
    first = "first-secret-plaintext"
    assert api_client.put(
        f"/accounts/{account['id']}/secrets/account_password", json={"value": first}
    ).status_code == 200
    (tmp_path / "config" / "credentials.key").unlink()
    second = "second-secret-must-not-leak"
    response = api_client.put(
        f"/accounts/{account['id']}/secrets/account_password", json={"value": second}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Account secret storage is unavailable"}
    assert first not in response.text + caplog.text
    assert second not in response.text + caplog.text


def test_delete_soft_archives_and_preserves_registry_row(
    api_client: TestClient, tmp_path: Path
) -> None:
    account = api_client.post("/accounts", json={"display_name": "Archive Me"}).json()
    assert api_client.delete(f"/accounts/{account['id']}").status_code == 204
    assert api_client.get(f"/accounts/{account['id']}").status_code == 404
    archived = api_client.get("/accounts?include_archived=true").json()
    assert archived["total"] == 1
    assert archived["items"][0]["status"] == "archived"
    assert archived["items"][0]["archived_at"] is not None


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
