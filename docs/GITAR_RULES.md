# Review rules for Gitar

Paste these into Gitar's repository rules (follow the Gitar dashboard for the exact place;
if it asks for files, put each rule in its own file under `.gitar/rules/`).

1. **Bounded searches.** Every Elasticsearch `search` call sets an explicit `size`, and every
   `rrf` retriever sets `rank_window_size`. Flag any that do not.
2. **Models and types move together.** If `api/hallway/models.py` changes, the same PR must
   update `web/src/api/schema.d.ts` by running `make types`. If CI fails on the `types` job,
   run `make types` and commit the result.
3. **No secrets.** No API keys, tokens or `.env` files in the repo. Secrets belong in `.env`
   locally and in the Kubernetes Secret `hallway-secrets`.
4. **Private fields stay private.** `secret` and `recovery_code` must never be returned by an
   endpoint other than the owner's own `Me` response. Flag any response model or log line that
   could expose them.
5. **Session, not parameters.** Endpoints that act for a person take the person from the
   session cookie (`current_attendee`), never from an id in the URL or body.
6. **Bounded metric labels.** Metric attributes only take values from a fixed set (room names
   from `ROOMS`, edge kinds). Never attendee ids or free text.
7. **Explain it simply.** This is a student project that must be explainable line by line.
   Flag abstractions, indirection or dependencies that a simpler version would not need.
