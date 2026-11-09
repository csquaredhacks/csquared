# Hallway contribution workflow

Ship every feature and fix on a branch through a pull request to `main`.
Read the affected code and PR discussion before changing behavior. Keep fixes
small and run the relevant existing checks. State checks that could not run.

Wait for Gitar's review and passing required CI before merging. Leave merging
to the team. Fix commits belong on the PR branch.

Read configuration from environment variables. Never print, commit, or copy
local secrets into PR comments, logs, test fixtures, or generated artifacts.
