"""Transactional ContentAsset operations built on private content storage."""

from __future__ import annotations

import re
import unicodedata
from typing import BinaryIO, Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ContentAsset,
    ContentAssetTag,
    ContentAssetVersion,
    ContentDelivery,
    ContentEvent,
)
from app.models.timestamps import utc_now
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.content_jobs import enqueue_content_inspection
from app.services.content_validation import (
    ContentValidationError,
    detect_content_signature,
    validate_content_hints,
)


_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,49}$")


class ContentAssetError(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


class ContentAssetService:
    def __init__(self, storage: ContentStorageService) -> None:
        self.storage = storage

    def create_upload(
        self,
        session: Session,
        *,
        stream: BinaryIO,
        original_filename: str,
        declared_mime_type: str | None,
        display_name: str,
        notes: str | None,
        tags: Iterable[str],
    ) -> ContentAsset:
        name = self._display_name(display_name)
        safe_notes = self._notes(notes)
        normalized_tags = self.normalize_tags(tags)
        staged = self.storage.stage_stream(stream)
        installed_key: str | None = None
        try:
            detected = detect_content_signature(self.storage.read_header(staged))
            safe_filename = validate_content_hints(
                original_filename, declared_mime_type, detected
            )
            with self.storage.maintenance_lock():
                materialized = self.storage.materialize_blob(session, staged, detected)
                installed_key = materialized.installed_storage_key
                asset = ContentAsset(
                    asset_type=detected.asset_type,
                    display_name=name,
                    notes=safe_notes,
                    source="upload",
                    status="processing",
                )
                session.add(asset)
                session.flush()
                version = ContentAssetVersion(
                    content_asset_id=asset.id,
                    version_number=1,
                    blob_id=materialized.blob.id,
                    original_filename=safe_filename,
                    detected_mime_type=detected.mime_type,
                    canonical_extension=detected.canonical_extension,
                    processing_status="processing",
                )
                session.add(version)
                session.flush()
                session.add_all(
                    ContentAssetTag(content_asset_id=asset.id, tag=tag)
                    for tag in normalized_tags
                )
                session.add(
                    ContentEvent(
                        content_asset_id=asset.id,
                        content_asset_version_id=version.id,
                        event_type="uploaded",
                        metadata_json={
                            "asset_type": detected.asset_type,
                            "mime_type": detected.mime_type,
                            "size_bytes": staged.size_bytes,
                            "sha256": staged.sha256,
                            "deduplicated": not materialized.created,
                        },
                    )
                )
                enqueue_content_inspection(session, version)
                session.commit()
                # The blob is now durable DB state, not a compensatable
                # uncommitted install if response loading later fails.
                installed_key = None
            return self.get(session, asset.id)
        except (ContentValidationError, ContentStorageError):
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            raise
        except IntegrityError as error:
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            raise ContentAssetError(
                "CONTENT_WRITE_CONFLICT", "Content upload conflicted with another request"
            ) from error
        except Exception:
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            raise
        finally:
            self.storage.discard_staged(staged)

    def create_replacement(
        self,
        session: Session,
        *,
        asset: ContentAsset,
        stream: BinaryIO,
        original_filename: str,
        declared_mime_type: str | None,
    ) -> ContentAsset:
        if asset.status == "deleted":
            raise ContentAssetError("CONTENT_DELETED", "Deleted content cannot be changed")
        staged = self.storage.stage_stream(stream)
        installed_key: str | None = None
        try:
            detected = detect_content_signature(self.storage.read_header(staged))
            safe_filename = validate_content_hints(
                original_filename, declared_mime_type, detected
            )
            if detected.asset_type != asset.asset_type:
                raise ContentValidationError(
                    "CONTENT_TYPE_MISMATCH",
                    "Replacement content type must match the asset",
                )
            with self.storage.maintenance_lock():
                materialized = self.storage.materialize_blob(session, staged, detected)
                installed_key = materialized.installed_storage_key
                next_number = int(
                    session.scalar(
                        select(func.coalesce(func.max(ContentAssetVersion.version_number), 0))
                        .where(ContentAssetVersion.content_asset_id == asset.id)
                    )
                    or 0
                ) + 1
                version = ContentAssetVersion(
                    content_asset_id=asset.id,
                    version_number=next_number,
                    blob_id=materialized.blob.id,
                    original_filename=safe_filename,
                    detected_mime_type=detected.mime_type,
                    canonical_extension=detected.canonical_extension,
                    processing_status="processing",
                )
                session.add(version)
                session.flush()
                session.add(
                    ContentEvent(
                        content_asset_id=asset.id,
                        content_asset_version_id=version.id,
                        event_type="version_added",
                        metadata_json={
                            "version_number": next_number,
                            "size_bytes": staged.size_bytes,
                            "sha256": staged.sha256,
                            "deduplicated": not materialized.created,
                        },
                    )
                )
                enqueue_content_inspection(session, version)
                session.commit()
                installed_key = None
            return self.get(session, asset.id)
        except (ContentValidationError, ContentStorageError):
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            raise
        except IntegrityError as error:
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            raise ContentAssetError(
                "CONTENT_WRITE_CONFLICT", "Content upload conflicted with another request"
            ) from error
        except Exception:
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            raise
        finally:
            self.storage.discard_staged(staged)

    def get(self, session: Session, asset_id: int) -> ContentAsset:
        asset = session.scalar(
            select(ContentAsset)
            .where(ContentAsset.id == asset_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(ContentAsset.tags),
                selectinload(ContentAsset.versions).selectinload(ContentAssetVersion.blob),
            )
        )
        if asset is None:
            raise ContentAssetError("CONTENT_NOT_FOUND", "Content asset was not found")
        return asset

    def update_metadata(
        self,
        session: Session,
        asset: ContentAsset,
        *,
        display_name: str | None,
        display_name_set: bool,
        notes: str | None,
        notes_set: bool,
        tags: Iterable[str] | None,
        archived: bool | None,
    ) -> ContentAsset:
        if asset.status == "deleted":
            raise ContentAssetError("CONTENT_DELETED", "Deleted content cannot be changed")
        metadata_changed = False
        if display_name_set:
            assert display_name is not None
            asset.display_name = self._display_name(display_name)
            metadata_changed = True
        if notes_set:
            asset.notes = self._notes(notes)
            metadata_changed = True
        if tags is not None:
            normalized = self.normalize_tags(tags)
            asset.tags[:] = [ContentAssetTag(tag=tag) for tag in normalized]
            metadata_changed = True
        if metadata_changed:
            session.add(
                ContentEvent(content_asset_id=asset.id, event_type="metadata_updated")
            )
        if archived is True and asset.status != "archived":
            asset.status = "archived"
            asset.archived_at = utc_now()
            session.add(ContentEvent(content_asset_id=asset.id, event_type="archived"))
        elif archived is False and asset.status == "archived":
            asset.status = self._restored_status(asset)
            asset.archived_at = None
            session.add(ContentEvent(content_asset_id=asset.id, event_type="restored"))
        session.commit()
        return self.get(session, asset.id)

    def soft_delete(self, session: Session, asset: ContentAsset) -> ContentAsset:
        if asset.status == "deleted":
            return asset
        active_delivery = session.scalar(
            select(ContentDelivery.id).where(
                ContentDelivery.content_asset_id == asset.id,
                ContentDelivery.status.in_(["pending", "delivering"]),
            )
        )
        if active_delivery is not None:
            raise ContentAssetError(
                "CONTENT_IN_USE", "Content has an active delivery"
            )
        asset.status = "deleted"
        asset.deleted_at = utc_now()
        asset.archived_at = None
        session.add(ContentEvent(content_asset_id=asset.id, event_type="deleted"))
        session.commit()
        return self.get(session, asset.id)

    @staticmethod
    def normalize_tags(tags: Iterable[str]) -> list[str]:
        normalized: set[str] = set()
        for raw in tags:
            if not isinstance(raw, str):
                raise ContentValidationError("INVALID_CONTENT_TAG", "Content tag is invalid")
            tag = " ".join(unicodedata.normalize("NFKC", raw).strip().lower().split())
            if not _TAG_PATTERN.fullmatch(tag):
                raise ContentValidationError("INVALID_CONTENT_TAG", "Content tag is invalid")
            normalized.add(tag)
        if len(normalized) > 20:
            raise ContentValidationError("INVALID_CONTENT_TAG", "Too many content tags")
        return sorted(normalized)

    @staticmethod
    def _display_name(value: str) -> str:
        name = " ".join(value.strip().split()) if isinstance(value, str) else ""
        if not 1 <= len(name) <= 255 or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise ContentValidationError(
                "INVALID_CONTENT_METADATA", "Content display name is invalid"
            )
        return name

    @staticmethod
    def _notes(value: str | None) -> str | None:
        if value is None:
            return None
        notes = value.strip()
        if len(notes) > 4000 or any(ord(c) == 0 for c in notes):
            raise ContentValidationError("INVALID_CONTENT_METADATA", "Content notes are invalid")
        return notes or None

    @staticmethod
    def _restored_status(asset: ContentAsset) -> str:
        if asset.current_version_id is not None:
            current = next(
                (version for version in asset.versions if version.id == asset.current_version_id),
                None,
            )
            if current is not None and current.processing_status == "ready":
                return "ready"
        latest = asset.versions[-1] if asset.versions else None
        return "invalid" if latest is not None and latest.processing_status == "invalid" else "processing"
