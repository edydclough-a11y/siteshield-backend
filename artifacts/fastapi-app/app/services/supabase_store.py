import logging
import os
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from app.schemas import IngestResult

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


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
        user = auth_response.user
        if user is None:
            raise ValueError("No authenticated user was returned.")
        client.postgrest.auth(credentials.credentials)
        return AuthenticatedSupabase(user_id=user.id, client=client)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="The Supabase access token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def save_site_record(
    authenticated: AuthenticatedSupabase,
    project_id: str,
    result: IngestResult,
    raw_text: str | None,
    media_mime_type: str | None,
) -> None:
    if result.category == "daily_log":
        table = "daily_logs"
        payload = {
            "project_id": project_id,
            "user_id": authenticated.user_id,
            "weather_summary": result.weather_summary,
            "headcount": result.headcount,
            "raw_transcript": raw_text or (
                f"Media upload ({media_mime_type})" if media_mime_type else result.summary_english
            ),
            "formatted_english_summary": result.summary_english,
        }
    elif result.category == "snag":
        table = "snags"
        payload = {
            "project_id": project_id,
            "plot_or_location": "Site Wide",
            "trade_assigned": result.trade_assigned,
            "description": result.summary_english,
            "severity": result.severity,
            "status": "Open",
        }
    else:
        table = "variations"
        title = result.summary_english.strip()
        if len(title) > 60:
            title = f"{title[:57].rstrip()}..."
        payload = {
            "project_id": project_id,
            "title": title,
            "description": result.summary_english,
            "delay_hours": result.delay_hours,
            "cost_impact_flag": result.cost_impact_flag,
            "estimated_cost": result.estimated_cost,
            "status": "Draft",
        }

    try:
        authenticated.client.table(table).insert(payload).execute()
    except Exception:
        logger.exception("Supabase insert failed for table %s.", table)
        raise HTTPException(
            status_code=502,
            detail=f"Supabase could not save this {result.category}. Check the table schema and row-level security policies.",
        ) from None