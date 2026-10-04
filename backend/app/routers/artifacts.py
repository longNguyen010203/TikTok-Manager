"""Controlled upload and associated download of managed Job artifacts."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, JobArtifact
from app.schemas.device_automation import ArtifactMetadata
from app.services.automation_artifacts import AutomationArtifactStore
from app.services.automation_errors import AutomationError

router = APIRouter(tags=["artifacts"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _metadata(artifact: JobArtifact) -> ArtifactMetadata:
    return ArtifactMetadata(
        id=artifact.id, job_id=artifact.job_id, kind=artifact.kind,
        filename=artifact.original_filename, mime_type=artifact.mime_type,
        size_bytes=artifact.size_bytes, sha256=artifact.sha256,
    )


@router.post("/artifacts", response_model=ArtifactMetadata, status_code=status.HTTP_201_CREATED)
async def upload_artifact(session: DatabaseSession, file: Annotated[UploadFile, File()]) -> ArtifactMetadata:
    store = AutomationArtifactStore.from_application_config()
    content_type = (file.content_type or "application/octet-stream").lower()
    allowed = {"image/png", "image/jpeg", "video/mp4", "text/plain", "application/octet-stream"}
    if content_type not in allowed:
        raise HTTPException(status_code=422, detail="Artifact MIME type is not allowed")
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > store.max_size_bytes:
            raise HTTPException(status_code=413, detail="Artifact exceeds the configured size limit")
        chunks.append(chunk)
    data = b"".join(chunks)
    if content_type == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=422, detail="Artifact content does not match its MIME type")
    if content_type == "image/jpeg" and not data.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=422, detail="Artifact content does not match its MIME type")
    if content_type == "video/mp4" and (len(data) < 12 or data[4:8] != b"ftyp"):
        raise HTTPException(status_code=422, detail="Artifact content does not match its MIME type")
    if content_type == "text/plain":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=422, detail="Text artifact is not valid UTF-8") from error
        if b"\x00" in data:
            raise HTTPException(status_code=422, detail="Text artifact contains invalid bytes")
    try:
        return _metadata(store.store_bytes(
            session, data=data, kind="upload", original_filename=file.filename or "upload.bin",
            mime_type=content_type,
        ))
    except AutomationError as error:
        raise HTTPException(status_code=422, detail={"code": error.code, "message": error.safe_message}) from error


@router.get("/jobs/{job_id}/artifacts/{artifact_id}")
def download_artifact(
    job_id: Annotated[int, Path(gt=0)], artifact_id: Annotated[int, Path(gt=0)],
    session: DatabaseSession,
) -> FileResponse:
    if session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    artifact = session.get(JobArtifact, artifact_id)
    if artifact is None or artifact.job_id != job_id or artifact.cleanup_status != "active":
        raise HTTPException(status_code=404, detail="Artifact not found for Job")
    store = AutomationArtifactStore.from_application_config()
    try:
        path = store.path_for(artifact)
    except AutomationError as error:
        raise HTTPException(status_code=404, detail="Artifact is unavailable") from error
    return FileResponse(path, media_type=artifact.mime_type, filename=artifact.original_filename)
