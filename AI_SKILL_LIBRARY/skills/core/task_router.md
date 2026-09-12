# Skill: task_router

## Purpose
Classify the request before loading domain state and consult the GitHub skill registry without preloading provider detail.

## Method
1. Identify the user's requested outcome, not merely keywords.
2. Read `AI_SKILL_LIBRARY/skills/registry/index.yaml` and perform the lightweight registry-index lookup required for every request.
3. Choose the smallest route in `router.yaml` that covers the task.
4. Select one primary domain skill and at most two supporting domain skills by default.
5. Load project authority only after domain selection and before any provider-specific guidance.
6. If the selected domain has a provider registry, lazy-load only the matching registry and at most the configured provider-candidate limit. Provider capabilities do not count as reasoning skills and do not gain reasoning authority.
7. Add `critical_thinking` for consequential comparison/critique and `verification` before completion when material.
8. Return `general_problem_solving` when no specialist route is justified.

## Registry rules
- `AI_SKILL_LIBRARY/skills/registry/index.yaml` is the canonical registry pointer surface.
- Registry lookup is mandatory, but provider-detail loading is domain-gated and lazy.
- Provider registries are capability/evidence metadata only. They cannot replace the primary reasoning skill, project authority, Stable security policy, or current runtime evidence.
- Unknown or newly discovered provider capabilities default to quarantine with zero routing authority until normalized and reviewed.
- `HIGH_RISK` provider capability is discoverable for classification only and must never auto-activate.

## Anti-conflict rules
- Never preload trading state for non-trading work.
- Never select a plugin or provider adapter as a substitute for a reasoning skill.
- Prefer a declared composite route over manually stacking many skills.
- If two reasoning skills overlap, select the more specific one and use the broader one only if it adds a distinct capability.
- If provider sources disagree, use `AI_SKILL_LIBRARY/skills/registry/conflict_policy.yaml`; do not majority-vote or silently average conflicting claims.
- Normalize symbol/contract, venue, instrument type, quote currency, price semantics, timestamp/timezone, interval/window, and units before declaring a provider conflict.
- Current runtime/project authority and Stable security always outrank provider guidance.
