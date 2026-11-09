# Enable Gitar for Hallway

## Repository configuration

- `.gitar/review/instructions.md` loads the conventions in `docs/GITAR_RULES.md`.
- `.gitar/instructions/workflow.md` applies the PR workflow to review and repair.
- `.gitar/rules/api-contract.md` posts an API compatibility checklist.
- `.gitar/rules/ci-failure.md` handles failed PR checks.
- `.github/pull_request_template.md` records the checks needed before merging.

These files configure Gitar. They do not install its GitHub App or enable
auto-apply by themselves.

## Activate and verify

1. Sign in at [Gitar](https://app.gitar.ai) with a repository administrator's account.
2. Connect the Gitar GitHub App to `csquaredhacks/csquared`.
3. Confirm the plan includes custom rules and automatic fixes.
4. Open every feature or fix as a PR targeting `main`.
5. Enable automatic fixes on each PR with the comment `gitar auto-apply:on`.
6. Confirm a Gitar review appears. Inspect Verification for the custom rule results.
7. When CI fails, confirm Gitar diagnoses it and validates any fix commit.
8. Merge only after review findings are resolved and required CI passes.

Use `gitar display:verbose` to inspect skipped rules. Record a real review and CI
repair in `docs/investigations/` once observed. Installation, review execution, and
automatic fixes remain unverified until those results appear.

References: [repository configuration](https://docs.gitar.ai/configuration/repository-config),
[rules](https://docs.gitar.ai/features/rules),
[CI repair](https://docs.gitar.ai/features/ci-failure-analysis).
