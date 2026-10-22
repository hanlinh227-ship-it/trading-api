# STACKHUB V2 — Account Integration Guide

This guide is for integrating accounts after signup/KYC/payment setup is already complete.

## 1. Put secrets outside Git

Use your deployment/system secret store. Current runtime secret names:

```bash
export TASKBOUNTY_API_KEY='your-real-key'
export GUMROAD_ACCESS_TOKEN='your-real-token'
export STACKHUB_SOLVER_COMMAND='/path/to/your/authorized-solver-wrapper'
```

Do not commit the values and do not paste them into chat, logs, YAML, issues or pull requests.

STACKHUB does **not** need your PayPal password, PayPal session, bank password, card/CVV, wallet seed phrase/private key, Adobe password, RapidAPI password or GitHub password/2FA recovery code. Link payout rails and complete account authorization inside the official platform.

## 2. Check all account integrations before runtime

From `stackhub_v2/`:

```bash
python -m pip install -e '.[test]'
python -m stackhub.account_doctor
stackhub doctor --config config/sources.yaml
```

`account_doctor` prints only integration mode, readiness and missing environment-variable names. It never prints secret values.

Current account modes:

- `taskbounty`: `AUTO` after current mutation capability verification; secret: `TASKBOUNTY_API_KEY`.
- `gumroad`: `OBSERVE`; secret: `GUMROAD_ACCESS_TOKEN`. Gumroad's current API can be used for supported account/product/sales operations, but current official documentation says creating/uploading products through the API is not supported, so new-product publishing remains `ASSISTED`.
- `rapidapi`: `ASSISTED` by default. Provider publishing/payout is managed in the official provider console; only enable REST Platform API automation when the account has explicit Platform API entitlement and the exact contract is verified.
- `adobe_stock`: `ASSISTED`; current contributor upload path is the Contributor Portal, so STACKHUB prepares/validates assets and metadata but does not invent an unsupported upload API.
- `paypal`: `PAYOUT_ONLY`; no PayPal credentials are requested by STACKHUB.
- `github`: `ASSISTED` authorization through approved deployment/tooling OAuth/App/CLI; repository credentials stay outside marketplace secrets.

## 3. Connect an authorized solver

Automatic work requires a solver process that reads one JSON object from stdin and writes one JSON object to stdout. Configure its command:

```bash
export STACKHUB_SOLVER_COMMAND='/path/to/your/authorized-solver-wrapper'
```

Expected stdout:

```json
{
  "artifact_reference": "https://artifact-or-pr-reference",
  "artifact_kind": "code",
  "evidence": {"tests": "passed", "summary": "..."}
}
```

The solver subprocess does not receive environment variables whose names look like API keys, tokens, secrets, passwords, private keys, seed phrases or mnemonics. Marketplace credentials remain in the orchestration/submission layer.

## 4. Verify read-only integration first

From `stackhub_v2/`:

```bash
stackhub doctor --config config/sources.yaml
stackhub scan-once --config config/sources.yaml
stackhub opportunities
stackhub status
```

Expected before live mutation: zero external spend, no secret values printed, and discovered opportunities appear only if enabled sources currently have eligible work.

## 5. First mutation: one task only

Copy `config/sources.live.example.yaml` to a deployment-only path. Do not put credentials in it. Keep `max_active_claims: 1` for the first real task.

Run:

```bash
stackhub doctor --config /etc/stackhub/sources.yaml
stackhub orchestrate-once --config /etc/stackhub/sources.yaml
stackhub status --config /etc/stackhub/sources.yaml
```

Review the resulting claim/submission on the marketplace. Only after a successful end-to-end cycle should continuous mode be enabled.

## 6. 24/7 runtime

After first-task verification:

```bash
stackhub run --config /etc/stackhub/sources.yaml --db /var/lib/stackhub/stackhub-v2.db
```

A systemd example is provided at `deploy/stackhub-v2.service.example`. Keep the SQLite DB on persistent storage and place environment variables in the deployment secret mechanism, not in the repository.

## 7. Adding more job/account sources

Each platform needs a real adapter implementing the common `discover`, and where explicitly permitted, `claim`, `submit`, `publish` and payout-observation interfaces. Add it to `adapter_registry.py` only after the platform's current API/terms/agent permission are verified.

If a platform requires human-only actions or has no supported automation path, keep it `ASSISTED` or `DISCOVERY_ONLY`; do not emulate a human, bypass CAPTCHA, scrape around restrictions or invent private APIs.

The core orchestrator does not need to change when a new compliant adapter is added.
