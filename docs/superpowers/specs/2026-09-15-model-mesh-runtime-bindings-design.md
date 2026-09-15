# Model Mesh Runtime Bindings Design

## Goal
Enable every Model Mesh provider that has a valid Cloudflare credential and an eligible FREE_ONLY model without mixing secret values into the canonical model-evidence snapshot.

## Architecture
Keep provider/model evidence and eligibility separate from execution bindings. Add two canonical artifacts:

1. `active.json` — the human/promoted FREE_ONLY model registry used to compile the production model snapshot. It contains only normalized model evidence and no runtime secrets or secret names.
2. `runtime_bindings.json` — maps `provider_id` to adapter family, endpoint URL, environment secret name, and optional account-id environment variable.

Runtime code joins a selected evidence-only model with its public binding immediately before provider execution. The production compiler must default to `active.json`; it must never silently replace the promoted pool with an empty candidate report.

No secret value is committed, serialized into a model snapshot, returned by health endpoints, or logged. Missing credentials produce `INTEGRATED_NOT_ACTIVE`; they never widen permissions or fall back to a paid provider.

## Canonical active registry
`active.json` is not an Evergreen discovery output. Discovery remains quarantine-only. A model enters `active.json` only after explicit free/free-account evidence and policy review. Models may be admitted as `degraded` before a live runtime smoke; `healthy` is reserved for runtime-verified health.

The initial active pool may include only providers with current free/free-account evidence. Providers without current entitlement or credentials remain represented in runtime bindings but absent from the active model registry.

## Canonical runtime bindings
The binding registry must cover: `groq`, `gemini_developer_api`, `cloudflare_workers_ai`, `openrouter`, `mistral`, `cohere`, `huggingface_inference_providers`, `nvidia_nim`, `cerebras`, `sambanova`, `alibaba_model_studio`, and `opencode_zen`.

Each binding contains only public execution metadata:
- `endpoint_family`
- `endpoint_url`
- `secret_name`
- optional `account_id_env`
- `enabled`

## Runtime rules
- FAST remains provider-free.
- SECRET data never leaves Brain.
- FREE_ONLY remains mandatory.
- A configured key does not imply model eligibility; model eligibility stays evidence-driven.
- Paid/unknown/expired models stay inactive.
- Missing NVIDIA or any other provider credential does not degrade the rest of the mesh.
- OpenCode Zen is eligible only for models explicitly identified as free/account-specific under current policy.
- Alibaba/Qwen is eligible only while its verified free quota/Free-Quota-Only policy is valid.
- No runtime binding may contain a secret value; only environment-variable names are allowed.

## Health and verification
Expose only provider configuration state (`configured: true/false`), binding state, and eligible model counts. Never expose credential values. Promotion requires unit tests, canonical CI, exact-SHA deployment, and production smoke checks. A provider becomes `PROVIDER_ACTIVE` only after both an eligible active model and the required runtime credential are present; live key/model success may upgrade its health from `degraded` to `healthy`.
