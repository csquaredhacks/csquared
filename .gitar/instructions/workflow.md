# Hallway contribution workflow

Read `docs/WORKING_PLAN.md` for current product scope and build order. Distinguish
planned flows from implemented behavior; `docs/API.md` is the current API contract.

Ship every feature and fix on a branch through a pull request to `main`.
Enable automatic fixes on each PR with the comment `gitar auto-apply:on` and
verify Gitar confirms the setting.
Read the affected code and PR discussion before changing behavior. Keep fixes
small and run the relevant existing checks. State checks that could not run.

Wait for Gitar's review and passing required CI before merging. Leave merging
to the team. Fix commits belong on the PR branch.

Read configuration from environment variables. Never print, commit, or copy
local secrets into PR comments, logs, test fixtures, or generated artifacts.
