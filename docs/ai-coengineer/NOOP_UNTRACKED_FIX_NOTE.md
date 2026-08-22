# AI loop untracked implementation guard finding

The DeepSeek implementer correctly treats newly-created allowed files as implementation results, but workflow-level `git diff --quiet` checks do not see untracked files. Manual fallback `ai-loop-wake.yml` was corrected to use `git status --porcelain --untracked-files=all` for the non-empty implementation guard. The canonical `ai-loop.yml` must use the same semantics so create-only tasks are not falsely rejected as `No implementation diff`.
