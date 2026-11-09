# Review rules for Gitar

These conventions load through `.gitar/review/instructions.md`. Repeatable actions
live separately in `.gitar/rules/`. See [Gitar setup](GITAR_SETUP.md) for activation
and verification.

1. **Bounded searches.** Every Elasticsearch `search` call sets an explicit `size`, and every
   `rrf` retriever sets `rank_window_size`. Flag any that do not.
2. **Models and types move together.** If `api/hallway/models.py` changes, the same PR must
   regenerate the OpenAPI-derived browser schema by running `make types` and update
   affected callers. Use the generated path defined by the actual Makefile. If CI
   fails on schema drift, run that target and commit the result.
3. **No secrets.** No API keys, tokens or `.env` files in the repo. Secrets belong in `.env`
   locally and in the Kubernetes Secret `hallway-secrets`.
4. **Private fields stay private.** Public profiles, graph responses, QR codes,
   and logs must never expose `secret` or `recovery_code`. Recovery codes may appear
   only in the owner's `Me` response. Session secrets belong only in the HttpOnly
   session cookie and server-side verification data, never in JSON responses.
5. **Session, not parameters.** Endpoints that act for a person take the person from the
   session cookie (`current_attendee`), never from an id in the URL or body.
6. **Bounded metric labels.** Metric attributes only take values from a fixed set (room names
   from `ROOMS`, edge kinds). Never attendee ids or free text.
7. **Explain it simply.** This is a student project that must be explainable line by line.
   Flag abstractions, indirection or dependencies that a simpler version would not need.
8. **Protect demo controls.** Changing chaos mode requires both `CHAOS_ENABLED=true`
   and a valid `X-Admin-Token`. Keep attendee session credentials out of telemetry.
