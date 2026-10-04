"""Content schema constraints and foreign-key behavior."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import (
    ContentAsset,
    ContentAssetTag,
    ContentAssetVersion,
    ContentBlob,
    ContentEvent,
)


@pytest.fixture
def content_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    init_db(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def add_foundation(session: Session):
    blob = ContentBlob(
        storage_key="a" * 32,
        sha256="b" * 64,
        size_bytes=10,
        detected_mime_type="image/png",
        status="active",
    )
    asset = ContentAsset(
        asset_type="image",
        display_name="Schema image",
        source="upload",
        status="processing",
    )
    session.add_all([blob, asset])
    session.flush()
    version = ContentAssetVersion(
        content_asset_id=asset.id,
        version_number=1,
        blob_id=blob.id,
        original_filename="image.png",
        detected_mime_type="image/png",
        canonical_extension=".png",
        processing_status="processing",
    )
    session.add(version)
    session.commit()
    return blob, asset, version


def test_blob_digest_and_storage_key_are_unique(content_session: Session) -> None:
    add_foundation(content_session)
    content_session.add(
        ContentBlob(
            storage_key="c" * 32,
            sha256="b" * 64,
            size_bytes=10,
            detected_mime_type="image/png",
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        content_session.commit()
    content_session.rollback()

    content_session.add(
        ContentBlob(
            storage_key="a" * 32,
            sha256="d" * 64,
            size_bytes=10,
            detected_mime_type="image/png",
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        content_session.commit()


def test_version_and_tag_uniqueness(content_session: Session) -> None:
    blob, asset, _version = add_foundation(content_session)
    content_session.add(
        ContentAssetVersion(
            content_asset_id=asset.id,
            version_number=1,
            blob_id=blob.id,
            original_filename="again.png",
            detected_mime_type="image/png",
            canonical_extension=".png",
            processing_status="processing",
        )
    )
    with pytest.raises(IntegrityError):
        content_session.commit()
    content_session.rollback()

    content_session.add_all(
        [
            ContentAssetTag(content_asset_id=asset.id, tag="same"),
            ContentAssetTag(content_asset_id=asset.id, tag="same"),
        ]
    )
    with pytest.raises(IntegrityError):
        content_session.commit()


def test_asset_delete_cascades_versions_tags_and_events_but_blob_is_restricted(
    content_session: Session,
) -> None:
    blob, asset, version = add_foundation(content_session)
    content_session.add_all(
        [
            ContentAssetTag(content_asset_id=asset.id, tag="schema"),
            ContentEvent(
                content_asset_id=asset.id,
                content_asset_version_id=version.id,
                event_type="uploaded",
            ),
        ]
    )
    content_session.commit()

    content_session.delete(blob)
    with pytest.raises(IntegrityError):
        content_session.commit()
    content_session.rollback()

    content_session.delete(asset)
    content_session.commit()
    assert content_session.scalar(select(func.count()).select_from(ContentAssetVersion)) == 0
    assert content_session.scalar(select(func.count()).select_from(ContentAssetTag)) == 0
    assert content_session.scalar(select(func.count()).select_from(ContentEvent)) == 0
    assert content_session.get(ContentBlob, blob.id) is not None
