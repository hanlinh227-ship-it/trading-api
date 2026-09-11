# Skill: task_router

## Purpose
Classify the request before loading domain state.

## Method
1. Identify the user's requested outcome, not merely keywords.
2. Choose the smallest route in `router.yaml` that covers the task.
3. Select one primary domain skill and at most two supporting domain skills by default.
4. Add `critical_thinking` for consequential comparison/critique and `verification` before completion when material.
5. Load project authority only after domain selection.
6. Return `general_problem_solving` when no specialist route is justified.

## Anti-conflict rules
- Never preload trading state for non-trading work.
- Never select a plugin as a substitute for a skill.
- Prefer a declared composite route over manually stacking many skills.
- If two candidate skills overlap, select the more specific one and use the broader one only if it adds a distinct capability.
