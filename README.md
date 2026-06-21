# Fill Contributions Graph

Explicit-only Codex skill for planning GitHub maintenance activity across repositories.

This skill is intentionally conservative: it plans first, writes an Excel review file, waits for explicit approval, and records every pushed commit and cleanup PR in manifests.

```text
GitHub account -> repo scan -> existing commit deduction -> Excel review -> approved execution
```

## What It Does

- Scans repositories owned by a target GitHub account or organization.
- Requires more than 10 eligible repositories before planning.
- Generates a deterministic activity plan for a date range.
- Subtracts commits that already exist on GitHub for each planned date.
- Writes an Excel review file before any execution.
- Supports manifest-driven push and per-repository cleanup PR workflows.

## Safety Rules

- Trigger only when the user explicitly names `fill-contributions-graph`.
- Do not create empty commits.
- Do not create fake placeholder code.
- Do not execute until the Excel plan is explicitly approved.
- Do not rewrite Git history unless the user explicitly confirms the affected repositories.
- Prefer one cleanup PR per affected repository. GitHub PRs cannot span multiple repositories.

## Planning

Generate a daily Excel review file:

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --profile vibe_coding_builder `
  --excel-out plan.xls
```

Generate one row per planned commit:

```powershell
python .\scripts\generate_plan.py `
  --account VectorPeak `
  --start 2026-03-01 `
  --end 2026-04-01 `
  --granularity commit `
  --excel-out commit-detail.xls `
  --out commit-detail.tsv
```

`--end` is exclusive. To include `2026-03-31`, pass `--end 2026-04-01`.

## Existing Commit Deduction

The plan counts existing author commits on GitHub for each active day:

```text
author:<author> author-date:<YYYY-MM-DD>..<YYYY-MM-DD> user:<account>
```

Then it plans only the remainder:

```python
planned_new_commit_count = max(0, target_commit_count - existing_author_commit_count)
```

## Cleanup PR Workflow

After the Excel plan is approved, the normal execution path is:

1. Create planned commits and push them to each repository default branch.
2. Verify every pushed commit is reachable from the remote default branch.
3. Create one cleanup branch per affected repository.
4. Delete manifest-owned generated docs from that repository.
5. Commit and push the cleanup branch.
6. Open one draft cleanup PR per repository.
7. Verify no manifest-owned generated docs remain on each cleanup PR branch.

A GitHub PR is scoped to one repository, so cross-repository cleanup requires one PR per affected repository.

Generated docs commonly live under:

```text
docs/notes/
docs/testing/
docs/config/
docs/maintenance/
docs/evaluation/
docs/editorial/
docs/experiments/
docs/review/
```

Delete manifest-owned generated files from those directories, and remove directories when they become empty.

## Operational Lesson

History rewriting is not the default workflow. Keep it only as incident recovery knowledge.

If an older run used `git revert` and the user later asks to remove those revert commits from GitHub-visible history, do not revert the reverts. That creates additional current-day commits. Use `git push --force-with-lease` only after explicit repository-by-repository confirmation, preserve legitimate later commits, verify the recorded revert SHAs are no longer reachable, and then return to the cleanup PR workflow.

## Files

```text
fill-contributions-graph/
|-- SKILL.md
|-- README.md
|-- LICENSE
|-- agents/
|   `-- openai.yaml
|-- references/
|   `-- activity-profiles.md
`-- scripts/
    `-- generate_plan.py
```
