# Skill: platform_engineering

Covers deployment, Cloudflare, Android, web applications, automation, and multi-agent coordination.

- Separate build artifact, source revision, deployment revision, and runtime health.
- Preserve environment/secret boundaries; never expose credentials in logs or docs.
- For mobile/web UX, verify lifecycle, connectivity, stale/offline states, and user-visible error recovery.
- For automation, make retries bounded, actions idempotent where possible, and state transitions observable.
- For AI-agent collaboration, designate one current authority and one writer at a time when shared state can conflict.
