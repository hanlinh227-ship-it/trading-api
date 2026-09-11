# Skill: debugging_tdd

Use for bugs, regressions, unexpected behavior, and behavior changes.

1. Collect direct evidence and identify the failing path.
2. Find root cause before patching symptoms.
3. For a behavior change, write a failing test first and confirm it fails for the intended reason.
4. Implement the smallest causal change.
5. Re-run the focused test and the relevant broader suite.
6. Refactor only after green tests.
7. Never claim fixed from code inspection alone when an executable verification is available.
