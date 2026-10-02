# FastAPI Starter

A small Python API service built with FastAPI and Uvicorn.

## Run in Replit

Start the **FastAPI App** workflow. It serves the API on port `8000`.

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
- `GET /docs` — interactive Swagger UI
- `GET /redoc` — ReDoc API reference

FastAPI generates the OpenAPI schema and interactive documentation automatically.