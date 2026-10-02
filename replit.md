# FastAPI Starter

A small Python API service built with FastAPI, with automatic interactive API documentation and a health endpoint.

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
- Main API: FastAPI + Uvicorn (`artifacts/fastapi-app`)
- Existing shared API: Express 5 (`artifacts/api-server`)
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `artifacts/fastapi-app/app/main.py` — FastAPI application and routes
- `artifacts/fastapi-app/README.md` — Python setup and endpoint guide
- `artifacts/api-server` — existing Express API service

## Architecture decisions

- FastAPI is a separate service so the existing Express API and generated TypeScript clients remain unchanged.

## Product

The FastAPI service exposes basic service information, a health check, and interactive API references at `/docs` and `/redoc`.

## User preferences

None recorded.

## Gotchas

- The FastAPI app has its own workflow and listens on port 8000.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
