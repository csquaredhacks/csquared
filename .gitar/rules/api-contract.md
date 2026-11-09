---
title: "Hallway API contract checklist"
description: "Keep public API changes aligned with the browser client and docs"
type: automation
when: "A PR changes public request or response models in api/hallway/models.py or endpoints under api/hallway/routes/"
actions: "Post or update one API contract checklist on the PR, with evidence for completed items"
---

# Check API compatibility

Inspect the diff and post one checklist covering:

- Public request and response shapes agree with `docs/API.md`.
- Changed OpenAPI schemas are regenerated using `make types`, and the browser
  callers agree with the generated output. Use the actual output path from the
  Makefile rather than assuming a filename.
- Existing API and browser checks pass, including coverage for changed behavior.
- Actions for an attendee use the session, not a caller-supplied acting id.

Mark items complete only when evidence supports them. Explain missing checks.
Update this rule's existing checklist on later commits instead of duplicating it.
