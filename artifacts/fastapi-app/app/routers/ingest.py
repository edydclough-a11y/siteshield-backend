import asyncio
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.schemas import Category, IngestResponse
from app.services.gemini import analyze_site_input
from app.services.media import (
    MAX_UPLOAD_BYTES,
    TEXT_TYPES,
    normalize_mime_type,
    prepare_media,
)
from app.services.supabase_store import (
    AuthenticatedSupabase,
    get_site_record,
    list_site_records,
    require_authenticated_user,
    save_site_record,
)

MAX_TEXT_CHARACTERS = 50_000
MAX_TEXT_FILE_BYTES = 64_000

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.get("", response_model=list[dict[str, Any]])
def list_ingested_site_records(
    project_id: str = Query(..., min_length=1, max_length=128),
    category: Category | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    authenticated: AuthenticatedSupabase = Depends(require_authenticated_user),
) -> list[dict[str, Any]]:
    return list_site_records(authenticated, project_id.strip(), category, limit)


@router.post("", response_model=IngestResponse)
async def ingest_site_data(
    project_id: str = Form(..., min_length=1, max_length=128),
    raw_text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    title: str | None = Form(default=None, max_length=200),
    source: str | None = Form(default=None, max_length=120),
    authenticated: AuthenticatedSupabase = Depends(require_authenticated_user),
) -> IngestResponse:
    site_text = (raw_text or "").strip()
    record_title = title.strip() if title and title.strip() else None
    record_source = source.strip() if source and source.strip() else None
    media_chunks = None
    media_mime_type = None

    if len(site_text) > MAX_TEXT_CHARACTERS:
        raise HTTPException(status_code=413, detail="Text input is limited to 50,000 characters.")

    if file is not None:
        media_mime_type = normalize_mime_type(file.content_type, file.filename)
        max_bytes = MAX_TEXT_FILE_BYTES if media_mime_type in TEXT_TYPES else MAX_UPLOAD_BYTES
        file_data = await file.read(max_bytes + 1)
        if len(file_data) > max_bytes:
            limit = "64 KiB" if media_mime_type in TEXT_TYPES else "8 MiB"
            raise HTTPException(status_code=413, detail=f"File uploads are limited to {limit}.")
        if not file_data:
            raise HTTPException(status_code=422, detail="The uploaded file is empty.")

        if media_mime_type in TEXT_TYPES:
            try:
                file_text = file_data.decode("utf-8").strip()
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=422,
                    detail="Text files must be encoded as UTF-8.",
                ) from None
            site_text = "\n\n".join(value for value in (site_text, file_text) if value)
        else:
            media_chunks = prepare_media(file_data, media_mime_type)

    if not site_text and not media_chunks:
        raise HTTPException(
            status_code=422,
            detail="Provide raw_text or upload a supported file.",
        )
    if len(site_text) > MAX_TEXT_CHARACTERS:
        raise HTTPException(status_code=413, detail="Combined text input is limited to 50,000 characters.")

    result = await asyncio.to_thread(analyze_site_input, site_text or None, media_chunks)
    await asyncio.to_thread(
        save_site_record,
        authenticated,
        project_id.strip(),
        result,
        site_text or None,
        media_mime_type,
        record_title,
        record_source,
    )
    return IngestResponse(
        status="success",
        category=result.category,
        result=result,
        title=record_title,
        source=record_source,
    )


@router.get("/{record_id}", response_model=dict[str, Any])
def get_ingested_site_record(
    record_id: str,
    project_id: str = Query(..., min_length=1, max_length=128),
    category: Category | None = Query(default=None),
    authenticated: AuthenticatedSupabase = Depends(require_authenticated_user),
) -> dict[str, Any]:
    record = get_site_record(
        authenticated,
        project_id.strip(),
        record_id,
        category,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Site record not found.")
    return record