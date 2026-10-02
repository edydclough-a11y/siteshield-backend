# SiteShield Omni-Ingest Engine

FastAPI service that classifies construction-site notes, photos, audio, and video as daily logs, snags, or variations, then saves the result to Supabase.

## Run in Replit

Start the **FastAPI App** workflow. It serves the API on port `8000`.

## Configure services

Add these values through Replit Secrets:

- `GEMINI_API_KEY` — Google Gemini API key. The service uses `gemini-2.5-flash` by default; optionally set `GEMINI_MODEL` to another available model.
- `SUPABASE_URL` — the root project URL, usually `https://<project-ref>.supabase.co`; do not append `/rest/v1/`.
- `SUPABASE_ANON_KEY` — the project's anon/publishable key.

Do not use a Supabase service-role key. The API requires a caller's Supabase access token and makes database requests with that user's token, so Supabase row-level security remains active.

The Supabase project must have the `daily_logs`, `snags`, and `variations` tables with these columns:

- `daily_logs`: `id`, `project_id`, `user_id`, `weather_summary`, `headcount`, `raw_transcript`, `formatted_english_summary`, `title`, `source`, `created_at`
- `snags`: `id`, `project_id`, `plot_or_location`, `trade_assigned`, `description`, `severity`, `status`, `title`, `source`, `created_at`
- `variations`: `id`, `project_id`, `title`, `description`, `delay_hours`, `cost_impact_flag`, `estimated_cost`, `status`, `source`, `created_at`

The `id` columns should identify a record, and `created_at` should be a timestamp used to sort list results. Optional `title` and `source` fields can be added to existing tables with `supabase/add_title_source_columns.sql`; review and run that SQL in Supabase only after confirming the tables exist.

Add RLS policies that let authenticated users read and insert records only for projects they can access. The API does not accept a client-supplied `user_id`; for daily logs it takes the user ID from the verified Supabase token. Any additional non-null columns in your schema need defaults or corresponding values in the insert code.

## Run locally

From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

## Endpoints

- `GET /` — service information
- `GET /health` — health check
- `POST /ingest` — analyze a site record and save it to Supabase
- `GET /ingest?project_id=...` — list recent records for a project; optionally filter with `category` and `limit`
- `GET /ingest/{record_id}?project_id=...` — fetch one record; optionally filter with `category`
- `GET /docs` — interactive Swagger UI
- `GET /redoc` — ReDoc API reference

FastAPI generates the OpenAPI schema and interactive documentation automatically.
Both read routes require `project_id` and the same bearer token as ingestion. The list is newest-first, defaults to 50 records, and accepts `limit` up to 100; `category` can be `daily_log`, `snag`, or `variation`. Supabase RLS remains the authority for which project records the caller can read.

### Ingest a record

`POST /ingest` accepts `multipart/form-data`:

- Required: `project_id`
- Optional: `raw_text`
- Optional: `file` (plain text, JPEG, PNG, WebP, supported audio, or supported video)
- Optional: `title` (up to 200 characters)
- Optional: `source` (up to 120 characters)
- Required header: `Authorization: Bearer <Supabase access token>`

Example:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -F "project_id=your-project-id" \
  -F "title=North corridor update" \
  -F "source=Mobile app" \
  -F "raw_text=The plastering team finished the north corridor."
```

List the most recent records in a project:

```bash
curl "http://127.0.0.1:8000/ingest?project_id=your-project-id&limit=50" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

Fetch one record:

```bash
curl "http://127.0.0.1:8000/ingest/record-id?project_id=your-project-id" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

Uploads are limited to 8 MiB; audio/video clips are limited to five minutes and are split into one-minute segments before analysis. Gemini retries transient errors and serializes calls to limit request bursts.

Audio/video processing requires `ffmpeg` and `ffprobe` on the machine running the service.

## Tests

From this directory, run `python -m unittest discover -s tests`. Tests use mocked Gemini/Supabase clients and do not call external services.