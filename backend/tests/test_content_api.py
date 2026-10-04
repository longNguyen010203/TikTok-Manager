"""Content library API tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.models import ContentAsset, ContentAssetTag, ContentBlob, ContentEvent
from tests.app_factory import create_test_app


PNG = b"\x89PNG\r\n\x1a\n" + b"api-png"
JPEG = b"\xff\xd8\xff\xe0" + b"api-jpeg"
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"api"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42"


@pytest.fixture
def content_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("TIKTOK_MANAGER_CONFIG", raising=False)
    monkeypatch.delenv("TIKTOK_MANAGER_CONTENT_ROOT", raising=False)
    monkeypatch.delenv("TIKTOK_MANAGER_CONTENT_MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.delenv("TIKTOK_MANAGER_CONTENT_MAX_TOTAL_BYTES", raising=False)
    database_url = URL.create(drivername="sqlite", database=str(tmp_path / "api.db"))
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    init_db(engine)
    application = create_test_app()
    application.state.testing_session = sessions

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


def upload(
    client: TestClient,
    *,
    data: bytes = PNG,
    filename: str = "photo.png",
    mime: str = "image/png",
    display_name: str = "Library Photo",
    notes: str | None = None,
    tags: list[str] | None = None,
):
    parts: list[tuple[str, tuple[str | None, bytes | str, str | None]]] = [
        ("file", (filename, data, mime)),
        ("display_name", (None, display_name, None)),
    ]
    if notes is not None:
        parts.append(("notes", (None, notes, None)))
    parts.extend(("tags", (None, tag, None)) for tag in tags or [])
    return client.post(
        "/content",
        files=parts,
    )


@pytest.mark.parametrize(
    ("data", "filename", "mime", "asset_type"),
    [
        (PNG, "photo.png", "image/png", "image"),
        (JPEG, "photo.jpeg", "image/jpeg", "image"),
        (WEBP, "photo.webp", "image/webp", "image"),
        (MP4, "clip.mp4", "video/mp4", "video"),
    ],
)
def test_upload_accepts_allowed_signatures_and_returns_processing_asset(
    content_api: TestClient, data, filename, mime, asset_type
) -> None:
    response = upload(
        content_api,
        data=data,
        filename=filename,
        mime=mime,
        display_name="Accepted Media",
        tags=[" Demo ", "demo", "Phase-2"],
    )

    assert response.status_code == 202
    body = response.json()
    assert body["asset_type"] == asset_type
    assert body["status"] == "processing"
    assert body["current_version"] is None
    assert body["tags"] == ["demo", "phase-2"]
    assert body["versions"][0]["processing_status"] == "processing"
    serialized = response.text
    assert "storage_key" not in serialized
    assert "content/blobs" not in serialized


def test_upload_rejects_empty_unsupported_mismatch_and_oversized(
    content_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = upload(content_api, data=b"")
    assert empty.status_code == 422
    assert empty.json()["detail"]["code"] == "EMPTY_CONTENT"

    unsupported = upload(content_api, data=b"MZ executable", filename="run.exe", mime="application/octet-stream")
    assert unsupported.status_code == 422
    assert unsupported.json()["detail"]["code"] == "UNSUPPORTED_CONTENT_TYPE"

    archive = upload(content_api, data=b"PK\x03\x04 archive", filename="data.zip", mime="application/zip")
    assert archive.status_code == 422

    mismatch = upload(content_api, data=PNG, filename="photo.jpg", mime="image/jpeg")
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "CONTENT_TYPE_MISMATCH"

    monkeypatch.setenv("TIKTOK_MANAGER_CONTENT_MAX_UPLOAD_BYTES", str(len(PNG) - 1))
    oversized = upload(content_api)
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "CONTENT_UPLOAD_TOO_LARGE"


def test_library_list_filters_ordering_and_pagination(content_api: TestClient) -> None:
    first = upload(content_api, display_name="Old image", tags=["campaign"]).json()
    second = upload(
        content_api,
        data=MP4,
        filename="clip.mp4",
        mime="video/mp4",
        display_name="Newest video",
        tags=["campaign", "video"],
    ).json()
    third = upload(content_api, data=JPEG, filename="other.jpg", mime="image/jpeg", display_name="Middle image").json()
    with content_api.app.state.testing_session() as session:
        session.get(ContentAsset, first["id"]).created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session.get(ContentAsset, second["id"]).created_at = datetime(2026, 1, 3, tzinfo=timezone.utc)
        session.get(ContentAsset, third["id"]).created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        session.commit()

    listed = content_api.get("/content?page=1&page_size=2").json()
    assert listed["total"] == 3
    assert [item["id"] for item in listed["items"]] == [second["id"], third["id"]]
    assert [item["id"] for item in content_api.get("/content?page=2&page_size=2").json()["items"]] == [first["id"]]
    assert [item["id"] for item in content_api.get("/content?asset_type=video").json()["items"]] == [second["id"]]
    assert [item["id"] for item in content_api.get("/content?tag=CAMPAIGN").json()["items"]] == [second["id"], first["id"]]
    assert [item["id"] for item in content_api.get("/content?query=middle").json()["items"]] == [third["id"]]
    assert content_api.get("/content?source=upload").json()["total"] == 3


def test_detail_patch_archive_restore_delete_and_events(content_api: TestClient) -> None:
    created = upload(content_api, tags=["old"]).json()
    asset_id = created["id"]
    detail = content_api.get(f"/content/{asset_id}")
    assert detail.status_code == 200
    assert len(detail.json()["versions"]) == 1
    assert len(content_api.get(f"/content/{asset_id}/versions").json()) == 1

    patched = content_api.patch(
        f"/content/{asset_id}",
        json={"display_name": "Updated", "notes": "safe note", "tags": ["New", "new"]},
    )
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Updated"
    assert patched.json()["tags"] == ["new"]

    archived = content_api.patch(f"/content/{asset_id}", json={"archived": True})
    assert archived.json()["status"] == "archived"
    assert content_api.get("/content").json()["total"] == 0
    assert content_api.get("/content?status=archived").json()["total"] == 1
    restored = content_api.patch(f"/content/{asset_id}", json={"archived": False})
    assert restored.json()["status"] == "processing"

    deleted = content_api.delete(f"/content/{asset_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert content_api.get("/content").json()["total"] == 0
    assert content_api.get("/content?status=deleted").json()["total"] == 1
    assert content_api.get(f"/content/{asset_id}/download").status_code == 410

    with content_api.app.state.testing_session() as session:
        assert session.scalar(select(func.count()).select_from(ContentBlob)) == 1
        assert session.scalar(select(func.count()).select_from(ContentAssetTag)) == 1
        event_types = list(
            session.scalars(
                select(ContentEvent.event_type)
                .where(ContentEvent.content_asset_id == asset_id)
                .order_by(ContentEvent.id)
            )
        )
        assert event_types == [
            "uploaded", "processing_queued", "metadata_updated",
            "archived", "restored", "deleted",
        ]


def test_duplicate_uploads_create_two_assets_and_one_blob(content_api: TestClient) -> None:
    first = upload(content_api, display_name="First").json()
    second = upload(content_api, display_name="Second").json()
    assert first["id"] != second["id"]
    with content_api.app.state.testing_session() as session:
        assert session.scalar(select(func.count()).select_from(ContentAsset)) == 2
        assert session.scalar(select(func.count()).select_from(ContentBlob)) == 1


def test_download_is_conflict_until_current_version_is_ready(content_api: TestClient) -> None:
    created = upload(content_api).json()
    asset_id = created["id"]
    pending = content_api.get(f"/content/{asset_id}/download")
    assert pending.status_code == 409
    assert pending.json()["detail"]["code"] == "CONTENT_NOT_READY"

    with content_api.app.state.testing_session() as session:
        asset = session.get(ContentAsset, asset_id)
        version = asset.versions[0]
        version.processing_status = "ready"
        asset.current_version_id = version.id
        asset.status = "ready"
        session.commit()

    downloaded = content_api.get(f"/content/{asset_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == PNG
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in downloaded.headers["content-disposition"]
