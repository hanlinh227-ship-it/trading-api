# Model Mesh Runtime Bindings Design

## Goal
Enable every Model Mesh provider that has a valid Cloudflare credential and an eligible FREE_ONLY model without mixing secret values into the canonical model-evidence snapshot.

## Architecture
Keep provider/model evidence and eligibility in the existing normalized Model Mesh snapshot. Add a separate runtime binding registry that maps `provider_id` to adapter family, endpoint URL, environment secret name, and optional account-id environment variable. Runtime code joins the selected model with its binding immediately before provider execution.

No secret value is committed, serialized into a snapshot, returned by health endpoints, or logged. Missing credentials produce `INTEGRATED_NOT_ACTIVE`; they never widen permissions or fall back to a paid provider.

## Canonical runtime bindings
The binding registry must cover: `groq`, `gemini_developer_api`, `cloudflare_workers_ai`, `openrouter`, `mistral`, `cohere`, `huggingface_inference_providers`, `nvidia_nim`, `cerebras`, `sambanova`, `alibaba_model_studio`, and `opencode_zen`.

Each binding contains only public execution metadata:
- `provider_id`
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
- OpenCode Zen remains inactive unless a model is explicitly verified free/account-specific under current policy.
- Alibaba/Qwen is eligible only while its verified free quota/Free-Quota-Only policy is valid.

## Health and verification
Expose only provider configuration state (`configured: true/false`) and eligible model counts. Never expose credential values. Promotion requires unit tests, canonical CI, exact-SHA deployment, and production smoke checks.
