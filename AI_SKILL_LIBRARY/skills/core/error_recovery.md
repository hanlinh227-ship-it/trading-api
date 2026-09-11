# Skill: error_recovery

Use for broken workflows, integration failures, and conflicts.

- Capture the exact symptom and last known-good state.
- Reproduce or obtain direct failure evidence before proposing a fix.
- Trace the data/control path backward to the earliest incorrect assumption or state transition.
- Change one causal layer at a time; avoid stacking speculative patches.
- Preserve recoverable state and credentials; do not reset persistent state as a shortcut.
- Verify the original failure no longer occurs and that adjacent behavior still works.
