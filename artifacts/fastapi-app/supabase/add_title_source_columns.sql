-- Add nullable metadata fields used by POST /ingest.
-- Run only after confirming the corresponding tables already exist.
ALTER TABLE public.daily_logs
    ADD COLUMN IF NOT EXISTS title text,
    ADD COLUMN IF NOT EXISTS source text;

ALTER TABLE public.snags
    ADD COLUMN IF NOT EXISTS title text,
    ADD COLUMN IF NOT EXISTS source text;

ALTER TABLE public.variations
    ADD COLUMN IF NOT EXISTS title text,
    ADD COLUMN IF NOT EXISTS source text;