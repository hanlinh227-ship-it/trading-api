# ChatGPT -> GitHub -> VPS -> 3AI Queue

Fallback transport for ChatGPT sessions that cannot mount the Cloudflare MCP tool directly.

Create one immutable JSON request under `runtime/3ai-queue/requests/<task-id>.json`:

```json
{
  "task_id": "unique-id",
  "instruction": "Analyze the supplied task using the same evidence package.",
  "context": "Optional evidence/context."
}
```

A push to `main` triggers `.github/workflows/chatgpt-3ai-task-queue.yml` on the `trading-vps` self-hosted runner. The runner calls the existing authenticated VPS bridge at `127.0.0.1:8789`, requests only `claude`, `codex`, and `deepseek`, requires quorum >=2/3, and uploads an auditable result artifact.

This is a transport fallback only. It MUST NOT create a second AI core, write live trading state, place orders, or expose secrets. Cloudflare MCP and this queue both converge on the same VPS 3AI bridge.

Do not overwrite an old request. Each request gets a new task ID/file. Old request files are evidence and may be cleaned later under retention policy after results are no longer needed.
