# CI failed because the browser types were not regenerated, and Gitar pushed the fix

- **When:** 13:47 to 13:50 Mountain Time (20:47 to 20:50 UTC), 9 November 2026
- **Planted or real:** real. Nobody set this up. The first push of a new feature forgot a step.
- **Where:** PR #7, "Add community signup and shareable Luma invitations",
  https://github.com/csquaredhacks/csquared/pull/7
- **Symptom:** CI run 10 on commit `c50bfba` failed. The `types` job failed at the step
  "Generated types must be committed", and the `web` job failed at `npm run build`.
  https://github.com/csquaredhacks/csquared/actions/runs/42696209884
- **Tool used:** Gitar, with auto-apply turned on for this PR
  (`gitar auto-apply:on`, https://github.com/csquaredhacks/csquared/pull/7#issuecomment-6751046310)

## What Gitar said

Inline finding on `api/hallway/models.py`, posted 20:47:36 UTC
(https://github.com/csquaredhacks/csquared/pull/7#discussion_r4517792642):

> `web/src/api/schema.d.ts` was not regenerated and has no Community entries. Those lookups
> fail to type-check, so the frontend build and the CI schema-drift check will fail. The repo
> rules say model changes must ship with the regenerated types.

It suggested `make types && git add web/src/api/schema.d.ts`. That is project rule 2 in
[GITAR_RULES.md](../GITAR_RULES.md) ("Models and types move together").

Its API contract checklist comment, posted 20:47:33 UTC, said the same thing as an open item
(https://github.com/csquaredhacks/csquared/pull/7#issuecomment-6751060227):

> `web/src/api/schema.d.ts` is not in this PR and contains no `Community`/`CommunityIn`
> schemas, but `client.ts` and `Community.tsx` import them from `./schema`. Run `make types`
> and commit the output.

## Root cause

The PR added the `Community` and `CommunityIn` models in `api/hallway/models.py`, and the web
code used them, but nobody ran `make types`. So `web/src/api/schema.d.ts` had no Community
types. The web build could not type-check, and CI's schema-drift check failed.

## Fix

Gitar pushed the fix itself. Commit `e4f6e26` "fix: regenerate community API types",
author `Gitar <noreply@gitar.ai>`, 20:49:14 UTC, adds 124 lines to `web/src/api/schema.d.ts`.
https://github.com/csquaredhacks/csquared/commit/e4f6e260e6f30f2c5f02a51e4d28281968819ee4

The inline finding now reads "Fixed in e4f6e26 via Gitar".

On the next run (run 11, https://github.com/csquaredhacks/csquared/actions/runs/42696596367)
the `types` and `web` jobs passed. The `api` job still failed at `ruff check`, which is a
separate lint problem. Matt's next commit `1127626` made run 12 green.

## Time to fix

About 2 minutes from the failed run (20:47:27 UTC) to Gitar's fix commit (20:49:14 UTC), and
under 3 minutes until `types` and `web` were green again (20:49:51 UTC).

## Other times Gitar caught something today

- **PR #7, CI on the wrong Elasticsearch license (real, CI diagnosis).** After Matt turned on
  real Elasticsearch tests, run 13 failed in the `api` job
  (https://github.com/csquaredhacks/csquared/actions/runs/42697830769). Its Elasticsearch log
  shows `license [...] mode [basic]`. At 20:59:34 UTC Gitar posted: "In ES 9.2, RRF is gated on
  an Enterprise license [...] so on basic it returns a 403 license-compliance error", and
  suggested `xpack.license.self_generated.type: trial`
  (https://github.com/csquaredhacks/csquared/pull/7#discussion_r4517912156). Commit `71ae602`
  (authored by Matt, 21:00:02 UTC) added exactly that line, and run 14 passed. Gitar marked
  it "Fixed via Gitar"; the commit itself is under Matt's name.
- **PR #15, health check went green too early (real, Gitar fix).**
  https://github.com/csquaredhacks/csquared/pull/15. Gitar found that `/healthz` "reports
  green as soon as the five indices exist" even if index setup has not finished, and proposed
  "a module flag that `ensure_indices_with_retry` sets on success" because it is "easier to
  explain line by line" (rule 7). Gitar pushed that change itself in `5f29a8e`
  "fix: report health only after index setup" (22:17:24 UTC), with tests. The changed docstring
  then needed the types regenerated and a lint fix, which Matt did in `92a559e` and `80ee880`;
  run 49 passed. Final review: https://github.com/csquaredhacks/csquared/pull/15#issuecomment-6753048287
- **PR #15, schema drift again (real, Gitar fix that raced a human fix).** Run 35 failed in
  `types` with "API models changed: run `make types` and commit"
  (https://github.com/csquaredhacks/csquared/actions/runs/42709189629). Gitar's checklist
  said "Run `make types` and commit `web/src/api/schema.d.ts`"
  (https://github.com/csquaredhacks/csquared/pull/15#issuecomment-6752830501) and pushed
  `82feb6c` "fix: regenerate OpenAPI TypeScript schema". At the same time Matt had reverted
  the docstring in `5183c10`, so after Gitar's merge commit `60f6dee` the schema no longer
  matched and run 38 failed. Matt fixed it in `b59d10d` "Align schema after concurrent CI
  fixes". Lesson: with auto-apply on, one fixer at a time.
- **PR #8, duplicate crew suggestions (real, Gitar fix, human follow-up).**
  https://github.com/csquaredhacks/csquared/pull/8. Gitar pushed `803ef7d` "fix: deduplicate
  concurrent crew suggestions", then `a5b2d72` and `f5a8085` for decline and accept races.
  Our privacy test then showed that `803ef7d` built the crew id from both attendee ids, which
  leaks who was suggested (rule 4). Commit `1110947` replaced it with an HMAC.
- **PR #2, CI did not enforce generated types (Gitar fix).**
  https://github.com/csquaredhacks/csquared/pull/2. Gitar pushed `54c2c36` "fix: enforce
  generated types and align image defaults", which changed `ci.yml`, the `Makefile`,
  `values.yaml`, and added 917 lines to `web/src/api/schema.d.ts`.
- **More Gitar commits on PR branches today** (not written up in detail): `1aa7ee0` on
  PR #20 (https://github.com/csquaredhacks/csquared/pull/20), `1bae62a` on PR #22
  (https://github.com/csquaredhacks/csquared/pull/22), `f297776` on PR #10
  (https://github.com/csquaredhacks/csquared/pull/10), `ada3a9a` on PR #25
  (https://github.com/csquaredhacks/csquared/pull/25).
