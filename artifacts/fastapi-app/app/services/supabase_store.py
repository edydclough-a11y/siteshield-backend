import logging
import os
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from app.schemas import Category, IngestResult

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)
CATEGORY_TABLES = {
    "daily_log": "daily_logs",
    "snag": "snags",
    "variation": "variations",
}


@dataclass(frozen=True)
class AuthenticatedSupabase:
    user_id: str
    client: Client


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedSupabase:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="A valid Supabase access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not anon_key:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY.",
        )

    try:
        client = create_client(supabase_url, anon_key)
        auth_response = client.auth.get_user(credentials.credentials)
    except Exception as error:
        status = getattr(error, "status", None) or getattr(error, "status_code", None)
        if status in {400, 401, 403}:
            raise HTTPException(
                status_code=401,
                detail="The Supabase access token is invalid or expired.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        logger.exception("Supabase access-token verification failed.")
        raise HTTPException(
            status_code=503,
            detail="Supabase authentication is temporarily unavailable.",
        ) from None

    user = auth_response.user
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="The Supabase access token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client.postgrest.auth(credentials.credentials)
    return AuthenticatedSupabase(user_id=user.id, client=client)


def save_site_record(
    authenticated: AuthenticatedSupabase,
    project_id: str,
    result: IngestResult,
    raw_text: str | None,
    media_mime_type: str | None,
    title: str | None = None,
    source: str | None = None,
) -> None:
    if result.category == "daily_log":
        table = CATEGORY_TABLES[result.category]
        payload = {
            "project_id": project_id,
            "user_id": authenticated.user_id,
            "weather_summary": result.weather_summary,
            "headcount": result.headcount,
            "raw_transcript": raw_text or (
                f"Media upload ({media_mime_type})" if media_mime_type else result.summary_english
            ),
            "formatted_english_summary": result.summary_english,
            "title": title,
            "source": source,
        }
    elif result.category == "snag":
        table = CATEGORY_TABLES[result.category]
        payload = {
            "project_id": project_id,
            "plot_or_location": "Site Wide",
            "trade_assigned": result.trade_assigned,
            "description": result.summary_english,
            "severity": result.severity,
            "status": "Open",
            "title": title,
            "source": source,
        }
    else:
        table = CATEGORY_TABLES[result.category]
        variation_title = title or result.summary_english.strip()
        if len(variation_title) > 200:
            variation_title = f"{variation_title[:197].rstrip()}..."
        payload = {
            "project_id": project_id,
            "title": variation_title,
            "description": result.summary_english,
            "delay_hours": result.delay_hours,
            "cost_impact_flag": result.cost_impact_flag,
            "estimated_cost": result.estimated_cost,
            "status": "Draft",
            "source": source,
        }

    try:
        authenticated.client.table(table).insert(payload).execute()
    except Exception:
        logger.exception("Supabase insert failed for table %s.", table)
        raise HTTPException(
            status_code=502,
            detail=f"Supabase could not save this {result.category}. Check the table schema and row-level security policies.",
        ) from None


def list_site_records(
    authenticated: AuthenticatedSupabase,
    project_id: str,
    category: Category | None,
    limit: int,
) -> list[dict[str, Any]]:
    categories = (
        [(category, CATEGORY_TABLES[category])]
        if category is not None
        else list(CATEGORY_TABLES.items())
    )

    try:
        records: list[dict[str, Any]] = []
        for record_category, table in categories:
            response = (
                authenticated.client.table(table)
                .select("*")
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            records.extend(
                {**row, "category": record_category}
                for row in (response.data or [])
            )
        records.sort(
            key=lambda row: str(row.get("created_at") or ""),
            reverse=True,
        )
        return records[:limit]
    except Exception:
        logger.exception("Supabase site-record list failed.")
        raise HTTPException(
            status_code=502,
            detail="Supabase could not list site records. Check the table schema and SELECT policies.",
        ) from None


def get_site_record(
    authenticated: AuthenticatedSupabase,
    project_id: str,
    record_id: str,
    category: Category | None,
) -> dict[str, Any] | None:
    categories = (
        [(category, CATEGORY_TABLES[category])]
        if category is not None
        else list(CATEGORY_TABLES.items())
    )

    try:
        for record_category, table in categories:
            response = (
                authenticated.client.table(table)
                .select("*")
                .eq("project_id", project_id)
                .eq("id", record_id)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if rows:
                return {**rows[0], "category": record_category}
        return None
    except Exception:
        logger.exception("Supabase site-record lookup failed.")
        raise HTTPException(
            status_code=502,
            detail="Supabase could not retrieve the site record. Check the table schema and SELECT policies.",
        ) from None