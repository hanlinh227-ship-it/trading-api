# AUTO-INTAKE V1 — GitHub Issue -> Pipeline Task

Status: IMPLEMENTED (STAGED_FOR_FIRST_REAL_TASK)

## Purpose

AUTO-INTAKE V1 safely converts GitHub issues explicitly marked as AI-loop tasks into canonical bounded pipeline tasks for the DeepSeek implementer. It is the entry point of the AI loop and enforces fail-closed validation before any implementation work begins.

## Discovery

- Only issues whose title contains `[AI-TASK]` are considered.
- The issue body must contain exactly one machine-readable block between `AI_TASK_JSON_BEGIN` and `AI_TASK_JSON_END`.
- The block must be valid JSON and contain all required fields from the AI LOOP PROTOCOL task contract.

## Validation (fail-closed)

- All required fields must be present and typed correctly.
- `allowed_paths` must be a non-empty list for any code-changing task.
- `forbidden_paths` must be a list; hard-forbidden paths (`.env`, `cloudflare-worker/.dev.vars`, `.git/`) are always rejected.
- `auto_merge` must be `false`; AUTO-INTAKE V1 never enables automatic merge or deployment.
- `base_sha` must be a 40-character hex SHA.
- `task_id` must match `[A-Za-z0-9._-]{3,64}`.
- `validation_commands` are scanned for dangerous shell patterns and rejected if found.
- The entire task JSON is scanned for secret patterns and rejected if any are found.
- Underspecified write tasks (missing `allowed_paths` or `acceptance_criteria`) fail closed.

## Idempotency

- Each accepted `task_id` is recorded in `.ai-intake/<task_id>.json`.
- Duplicate issues for the same `task_id` are skipped and reported as `DUPLICATE_SKIPPED`.
- No duplicate task files are created.

## GitHub status reporting

Durable status is reported as a comment and label on the issue:

- `RECEIVED` — task accepted and validated
- `READY` — task file written for the implementer
- `FAILED` — validation or processing failed
- `DUPLICATE_SKIPPED` — task already processed

## Output

Validated tasks are written to `.ai-intake/tasks/<task_id>.json` for the DeepSeek implementer to consume.

## Safety invariants

- No automatic merge or deployment.
- No trading execution or risk logic modification.
- No secret exposure.
- No arbitrary shell execution from issue text.
- Stale-base and WRITE_LOCK checks remain enforced downstream.
