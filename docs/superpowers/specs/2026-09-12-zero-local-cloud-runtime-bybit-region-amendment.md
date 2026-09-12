# Zero-Local Cloud Runtime — Bybit Regional Restriction Amendment

**Date:** 2026-09-12  
**Parent spec:** `docs/superpowers/specs/2026-09-12-zero-local-cloud-runtime-design.md`

## Evidence discovered during implementation

The live credentialless smoke test ran the built gateway on a GitHub Actions runner in `westus2`.

Observed provider health:
- Binance: healthy
- OKX: healthy
- Gate: healthy
- KuCoin: healthy
- Bybit: HTTP 403

Bybit's current official V5 Integration Guidance states that IP addresses located in the United States or Mainland China are restricted and return HTTP 403. Therefore the Bybit failure is an external provider-region restriction, not a gateway schema or authentication defect.

## Safety decision

The zero-local runtime must **not** bypass this restriction with proxies, region-hopping tricks, undocumented mirrors, or user-side local execution.

Bybit remains registered as a `RESEARCH_SAFE` public-market capability, but runtime health must classify the known 403 case as:

`region_restricted_bybit_cloud_region`

## Amended acceptance rule

For Binance, OKX, Gate and KuCoin, the deployment requires a successful live public probe.

For Bybit, either of the following is acceptable:
1. the current cloud region is permitted by Bybit and the public probe is healthy; or
2. the current cloud region is restricted by Bybit and health reports exactly `region_restricted_bybit_cloud_region`.

Any other Bybit error remains a deployment failure.

This amendment does not widen permissions, enable credentials, add a fallback proxy, or change reasoning authority. It makes the deployment contract comply with the provider's published access policy while preserving zero-local execution.
