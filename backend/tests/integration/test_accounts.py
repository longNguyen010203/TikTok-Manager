"""End-to-end integration coverage for the Account CRUD API."""

from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models import Account
from tests.integration.conftest import IntegrationEnvironment

pytestmark = pytest.mark.integration


def account_payload(index: int, account_status: str = "active") -> dict[str, str]:
    return {
        "name": f"Integration Account {index}",
        "username": f"integration{index}",
        "platform": "tiktok",
        "status": account_status,
        "notes": f"Integration notes {index}",
    }


def create_account(
    environment: IntegrationEnvironment,
    index: int,
    account_status: str = "active",
) -> dict[str, Any]:
    response = environment.client.post(
        "/accounts", json=account_payload(index, account_status)
    )
    assert response.status_code == 201
    return response.json()


def test_create_account_persists_to_isolated_database(
    integration_environment: IntegrationEnvironment,
) -> None:
    created = create_account(integration_environment, 1)

    assert integration_environment.database_path.exists()
    assert integration_environment.database_path.name == "integration.db"
    with Session(integration_environment.engine) as session:
        persisted = session.get(Account, created["id"])
        assert persisted is not None
        assert persisted.name == "Integration Account 1"
        assert persisted.username == "integration1"


def test_list_accounts(integration_environment: IntegrationEnvironment) -> None:
    first = create_account(integration_environment, 1)
    second = create_account(integration_environment, 2)

    response = integration_environment.client.get("/accounts")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [item["id"] for item in body["items"]] == [first["id"], second["id"]]


def test_get_account_by_id(integration_environment: IntegrationEnvironment) -> None:
    created = create_account(integration_environment, 1)

    response = integration_environment.client.get(f"/accounts/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_update_account(integration_environment: IntegrationEnvironment) -> None:
    created = create_account(integration_environment, 1)

    response = integration_environment.client.patch(
        f"/accounts/{created['id']}",
        json={"name": "Updated Integration Account", "notes": None},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Updated Integration Account"
    assert updated["notes"] is None
    assert updated["username"] == created["username"]
    with Session(integration_environment.engine) as session:
        persisted = session.get(Account, created["id"])
        assert persisted is not None
        assert persisted.name == "Updated Integration Account"
        assert persisted.notes is None


def test_delete_account(integration_environment: IntegrationEnvironment) -> None:
    created = create_account(integration_environment, 1)

    response = integration_environment.client.delete(f"/accounts/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    with Session(integration_environment.engine) as session:
        assert session.get(Account, created["id"]) is None


def test_account_pagination(integration_environment: IntegrationEnvironment) -> None:
    created = [create_account(integration_environment, index) for index in range(1, 6)]

    response = integration_environment.client.get("/accounts?page=2&page_size=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert [item["id"] for item in body["items"]] == [
        created[2]["id"],
        created[3]["id"],
    ]


def test_account_status_filtering(
    integration_environment: IntegrationEnvironment,
) -> None:
    create_account(integration_environment, 1, "active")
    inactive = create_account(integration_environment, 2, "inactive")
    create_account(integration_environment, 3, "active")

    response = integration_environment.client.get("/accounts?status=inactive")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [inactive["id"]]
    assert all(item["status"] == "inactive" for item in body["items"])


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/accounts",
            {"name": "Missing fields", "username": "incomplete"},
        ),
        ("post", "/accounts", account_payload(1) | {"name": "   "}),
        ("get", "/accounts?page=0", None),
        ("get", "/accounts?page_size=101", None),
    ],
)
def test_invalid_input_returns_422(
    integration_environment: IntegrationEnvironment,
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    response = integration_environment.client.request(method, path, json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_account_returns_404(
    integration_environment: IntegrationEnvironment, method: str
) -> None:
    payload = {"name": "Not found"} if method == "patch" else None

    response = integration_environment.client.request(
        method, "/accounts/999999", json=payload
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Account not found"}
