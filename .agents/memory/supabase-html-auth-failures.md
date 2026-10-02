---
name: Supabase HTML auth failures
description: Diagnose HTML responses and JSON parse errors from Supabase authentication requests.
---

If a Supabase authentication request returns HTML and fails while parsing JSON, check that the configured URL is the project root and not a route such as `/rest/v1/`. The Supabase client appends its own Auth and REST paths; an invalid user token normally produces a structured authentication error instead.

**Why:** A REST-specific URL sent authentication to the wrong route and made a configuration error look like an upstream authentication failure.

**How to apply:** When Supabase auth receives HTML or a JSON parse error, verify the base URL path before changing keys or tokens.