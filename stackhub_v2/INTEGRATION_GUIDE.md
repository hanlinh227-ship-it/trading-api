# STACKHUB V2 — Account Integration Guide

This guide is for integrating accounts after signup/KYC/payment setup is already complete.

## 1. Keep secrets outside Git

Use your deployment/system secret store. At minimum for the current TaskBounty adapter:

```bash
export TASKBOUNTY_API_KEY='your-real-key'
```

Do not commit the value. Do not paste it into chat, logs, YAML, issues or pull requests.

STACKHUB does **not** need your PayPal password, PayPal session, bank password, wallet seed phrase or private key. Link PayPal/bank payout inside each marketplace. If a marketplace accepts a crypto payout address, only a public receiving address may be configured.

## 2. Connect an authorized solver

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

## 3. Verify read-only integration first

From `stackhub_v2/`:

```bash
python -m pip install -e '.[test]'
stackhub doctor --config config/sources.yaml
stackhub scan-once --config config/sources.yaml
stackhub opportunities
stackhub status
```

Expected before live mutation: zero external spend, TaskBounty adapter loaded, no secret values printed, and discovered opportunities appear only if the source currently has eligible jobs.

## 4. First mutation: one task only

Copy `config/sources.live.example.yaml` to a deployment-only path. Do not put credentials in it. Keep `max_active_claims: 1` for the first real task.

Run:

```bash
stackhub doctor --config /etc/stackhub/sources.yaml
stackhub orchestrate-once --config /etc/stackhub/sources.yaml
stackhub status
```

Review the resulting claim/submission on the marketplace. Only after a successful end-to-end cycle should you run continuously.

## 5. 24/7 runtime

After first-task verification:

```bash
stackhub run --config /etc/stackhub/sources.yaml --db /var/lib/stackhub/stackhub-v2.db
```

A systemd example is provided at `deploy/stackhub-v2.service.example`. Keep the SQLite DB on persistent storage.

## 6. Adding other accounts/sources

Each platform needs a real adapter implementing the common `discover`, and where permitted, `claim`/`submit`/payout-observation interfaces. Add it to `adapter_registry.py` only after the platform's current automation/API/terms are verified. If a platform requires human-only actions or has no supported automation path, keep it `ASSISTED` or `DISCOVERY_ONLY`; do not emulate a human or scrape around restrictions.

The core orchestrator does not need to change when a new compliant adapter is added.
