# SiteShield Omni-Ingest Engine

A Python API for turning construction-site notes and media into structured daily logs, snags, and variations saved to Supabase.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the existing API server (port 8080)
- `pnpm --filter @workspace/fastapi-app run dev` — run the FastAPI service (port 8000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, Python 3.11
- Main API: FastAPI + Uvicorn + Google Gen AI (`artifacts/fastapi-app`)
- Existing shared API: Express 5 (`artifacts/api-server`)
- Site-record storage: Supabase Python client using caller JWTs and RLS
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `artifacts/fastapi-app/app/main.py` — FastAPI application and health routes
- `artifacts/fastapi-app/app/routers/ingest.py` — authenticated ingestion and project-scoped record routes
- `artifacts/fastapi-app/app/services/supabase_store.py` — caller-scoped Supabase reads and writes
- `artifacts/fastapi-app/README.md` — setup, authentication, and endpoint guide
- `artifacts/api-server` — existing Express API service

## Architecture decisions

- FastAPI is a separate service so the existing Express API and generated TypeScript clients remain unchanged.
- Supabase writes use the caller's verified JWT and anon key; database row-level security must restrict records to authorized projects.

## Product

The FastAPI service analyzes site notes and supported media with Gemini, then saves classified daily logs, snags, and variations to Supabase. Authenticated callers can also list and fetch project records through Supabase RLS. Interactive API references are at `/docs` and `/redoc`.

## User preferences

None recorded.

## Gotchas

- The FastAPI app has its own workflow and listens on port 8000.
- Configure `GEMINI_API_KEY`, `SUPABASE_URL` (the project root URL, without `/rest/v1/`), and `SUPABASE_ANON_KEY` through Replit Secrets before using `POST /ingest`.
- Ingestion and read routes use the caller's Supabase token; RLS must scope reads and writes to authorized projects.
- Audio/video uploads require ffmpeg/ffprobe and are split into short segments before Gemini analysis.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
