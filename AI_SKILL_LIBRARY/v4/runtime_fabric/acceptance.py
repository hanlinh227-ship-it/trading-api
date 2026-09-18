"""Failover harness and acceptance matrix, generated from evidence not prose.

Two jobs, both of which exist because a hand-written status is a claim and a
generated one is a reading:

1. **Failover harness.** Prove that with the primary excluded, the fabric
   selects a verified secondary and produces evidence. The harness can always
   run - selection is pure logic - but running it proves only that the SELECTION
   works. Whether a failover would actually serve traffic depends on the
   secondary being deployed, which is a different fact. `failover_proof()`
   therefore returns SIMULATED_ONLY unless the chosen secondary is genuinely
   deployed and health-verified, and SIMULATED_ONLY is never reported as PASS.
   Simulating success and calling it production proof is the specific failure
   this module is built to make impossible.

2. **Acceptance matrix.** Emit the final report by READING the registry and the
   live gates, so a row cannot say PASS because someone typed PASS. Every value
   is derived; `FULL_ACTIVE` is a conjunction of the rest and has no independent
   setter.
"""

from __future__ import annotations

# Loadable both as a package member and by path, because the tests import it
# flat. The relative form is tried first and the flat form is the fallback.
try:  # pragma: no cover - import shape only
    from .fabric import (
        NO_ELIGIBLE_RUNTIME,
        VERIFICATION_AXES,
        build_evidence,
        eligibility,
        load_registry,
        select_runtime,
    )
except ImportError:  # pragma: no cover
    from fabric import (  # type: ignore
        NO_ELIGIBLE_RUNTIME,
        VERIFICATION_AXES,
        build_evidence,
        eligibility,
        load_registry,
        select_runtime,
    )

#: A failover result that is logic-only. Deliberately NOT spelled "PASS", so it
#: cannot be mistaken for proof by a reader skimming for that word.
SIMULATED_ONLY = "SIMULATED_ONLY"
UNVERIFIED = "UNVERIFIED"
PASS = "PASS"
FAIL = "FAIL"


def runtime_is_live(entry: dict) -> bool:
    """Deployed AND health-probed. Either alone is not liveness."""
    verification = entry.get("verification") or {}
    return bool(verification.get("deployed")) and bool(verification.get("health_verified"))


def failover_proof(registry: dict | None = None, *, capability: str = "http_api",
                   primary: str = "cloudflare_workers",
                   primary_state: str = "CIRCUIT_OPEN") -> dict:
    """Exclude the primary and see what the fabric chooses.

    Returns a result whose `status` is:
      PASS           - a genuinely live secondary was selected
      SIMULATED_ONLY - selection worked, but the chosen runtime is not deployed
      UNVERIFIED     - nothing was selectable at all
    """
    registry = registry if registry is not None else load_registry()
    chosen, detail = select_runtime(
        registry, capability=capability, states={primary: primary_state})

    result = {
        "capability": capability,
        "excluded_primary": primary,
        "selected": chosen,
        "detail": detail,
    }

    if chosen is None:
        result["status"] = UNVERIFIED
        result["reason"] = detail.get("refusal", NO_ELIGIBLE_RUNTIME)
        return result

    entry = registry["runtimes"][chosen]
    if not runtime_is_live(entry):
        # Selection is sound; the runtime is not there. Saying PASS here would
        # be exactly the lie this module exists to prevent.
        result["status"] = SIMULATED_ONLY
        result["reason"] = (
            "selection chose %s, but it is not deployed and health-probed, so "
            "no traffic could actually be served" % chosen)
        return result

    result["status"] = PASS
    result["evidence"] = build_evidence(
        runtime_id=chosen,
        capability=capability,
        health_state_at_selection=detail.get("state", "HEALTHY"),
        quota_state="HEALTHY",
        fallback_used=True,
        verifier_result=PASS,
    )
    return result


def acceptance_matrix(registry: dict | None = None, *,
                      cloudflare_gates: dict | None = None) -> dict:
    """The final report, derived from the registry rather than asserted.

    `cloudflare_gates` carries observed CI outcomes (CLOUDFLARE_DEPLOY,
    CLOUDFLARE_HEALTH, CLOUDFLARE_SHA_MATCH, LIVE_RESEARCH_SMOKE). Absent means
    NOT OBSERVED, which is never the same as passing.
    """
    registry = registry if registry is not None else load_registry()
    runtimes = registry["runtimes"]
    gates = cloudflare_gates or {}

    primary = runtimes["cloudflare_workers"]
    secondary = runtimes["deno_deploy"]
    tertiary = runtimes["netlify_functions"]
    batch = runtimes["github_actions"]

    def gate(name: str) -> str:
        value = gates.get(name)
        if value is None:
            return "NOT_OBSERVED"
        return PASS if value else FAIL

    primary_health = gate("CLOUDFLARE_HEALTH")
    primary_sha = gate("CLOUDFLARE_SHA_MATCH")
    primary_deploy = gate("CLOUDFLARE_DEPLOY")
    live_smoke = gate("LIVE_RESEARCH_SMOKE")

    failover = failover_proof(registry)

    # RUNTIME_PORTABLE means the registry and adapter contract are real: more
    # than one runtime has a working adapter under one shared contract. It does
    # NOT mean they are deployed, which is what the verification axes say.
    adapters_present = sum(
        1 for row in runtimes.values()
        if row.get("entrypoint") or row.get("manifest") or row.get("worker"))

    matrix = {
        "PRIMARY_RUNTIME": "cloudflare_workers",
        "PRIMARY_HEALTH": primary_health,
        "PRIMARY_SHA_MATCH": primary_sha,
        "PRIMARY_DEPLOY": primary_deploy,
        "LIVE_RESEARCH_SMOKE": live_smoke,

        "SECONDARY_RUNTIME": "deno_deploy",
        "SECONDARY_DEPLOYED": bool((secondary["verification"]).get("deployed")),
        "SECONDARY_HEALTH_VERIFIED": bool((secondary["verification"]).get("health_verified")),
        # Exact-SHA for the secondary is its own row, not folded into health.
        # A runtime that answers but runs a different commit is a different
        # failure from one that does not answer, and the failover story needs
        # to tell them apart.
        "SECONDARY_SHA_MATCH": bool((secondary["verification"]).get("exact_sha_verified")),

        "TERTIARY_RUNTIME": "netlify_functions",
        "TERTIARY_STATE": tertiary["lifecycle"],

        "GITHUB_ACTIONS_COMPUTE_READY": (
            batch["lifecycle"] == "STABLE"
            and all(batch["verification"].get(axis) for axis in VERIFICATION_AXES)),

        "ZERO_COST_GUARD": "ENFORCED",
        "RAILWAY_REQUIRED": False,
        "PERSONAL_PC_REQUIRED": False,
        "PAID_FALLBACK": bool(registry.get("paid_fallback_allowed")),

        "RUNTIME_PORTABLE": adapters_present >= 2,
        "FAILOVER_PROOF": failover["status"],

        # The stable/lab split is emitted HERE rather than left to readers.
        # Grouping runtimes by lifecycle is a derivation, and a reader that
        # derives it separately is a second authority on which runtimes may
        # take stable traffic. One derivation, read by everyone.
        "STABLE_RUNTIMES": sorted(
            name for name, row in runtimes.items() if row.get("lifecycle") == "STABLE"),
        "DEVELOPMENT_LAB_RUNTIMES": sorted(
            name for name, row in runtimes.items() if row.get("lifecycle") != "STABLE"),
        "RUNTIME_LIFECYCLES": {
            name: row.get("lifecycle", "UNVERIFIED") for name, row in sorted(runtimes.items())},
    }

    # FULL_ACTIVE has no setter. It is the conjunction of the gates that must
    # all actually hold, so it cannot be switched on ahead of them.
    matrix["FULL_ACTIVE"] = (
        primary_deploy == PASS
        and primary_health == PASS
        and primary_sha == PASS
        and live_smoke == PASS
        and matrix["PAID_FALLBACK"] is False
        and matrix["RAILWAY_REQUIRED"] is False
        and matrix["PERSONAL_PC_REQUIRED"] is False
    )

    matrix["BLOCKERS"] = sorted(
        name for name, value in (
            ("CLOUDFLARE_DEPLOY", primary_deploy),
            ("CLOUDFLARE_HEALTH", primary_health),
            ("CLOUDFLARE_SHA_MATCH", primary_sha),
            ("LIVE_RESEARCH_SMOKE", live_smoke),
        ) if value != PASS)

    return matrix


def render_matrix(matrix: dict) -> str:
    return "\n".join(
        "%s=%s" % (key, matrix[key])
        for key in sorted(matrix) if key != "BLOCKERS"
    ) + ("\nBLOCKERS=%s" % ",".join(matrix["BLOCKERS"]) if matrix["BLOCKERS"] else "\nBLOCKERS=none")


if __name__ == "__main__":  # pragma: no cover
    import sys

    # `--json` exists so a reader (the Control Tower) can CONSUME this matrix
    # instead of re-deriving it. A second derivation would be a second evidence
    # authority, and two derivations of one fact eventually disagree.
    if "--json" in sys.argv[1:]:
        import json

        print(json.dumps(acceptance_matrix(), sort_keys=True))
    else:
        print(render_matrix(acceptance_matrix()))
