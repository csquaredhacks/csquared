---
title: "Hallway CI repair"
description: "Diagnose failed PR checks and repair failures introduced by the change"
type: automation
when: "CI fails on the latest commit of an open pull request targeting main"
actions: "Explain the root cause and apply a focused repair when auto-apply is enabled; otherwise propose the repair"
---

# Repair the cause of CI failures

Read the failing job's logs and determine whether the PR caused the failure.
For a related failure, make the smallest correction on the PR branch when
auto-apply is enabled. Run the relevant existing checks and report the result.
For an unrelated or uncertain failure, report the evidence and remaining blocker.

For generated API schema drift, use `make types` and commit its actual output.
Do not hand-edit generated files, disable tests, weaken checks, expose secrets,
or merge the PR as a way to make CI pass.
