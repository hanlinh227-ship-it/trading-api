from g9.manifest import build_evidence_manifest, compute_manifest_hash, validate_evidence_manifest
from g9.system_contract import SYSTEM_CONTRACT_VERSION


def _g8_snapshot():
    return {
        "schema_version": 1,
        "kind": "g8_trading_research_evidence",
        "research_only": True,
        "authority": {"execution": "none", "production_strategy": "BYBIT-BTC-STATEFLOW-2.1"},
        "source_sha": "abc123",
        "data_cutoff": "2026-09-12",
        "snapshot_hash": "a" * 64,
        "symbols": {
            "BTCUSDT": {
                "profile_hash": "btc-profile",
                "status": "RESEARCH_ONLY",
                "production_execution_authority": False,
            },
            "SOLUSDT": {
                "profile_hash": "sol-profile",
                "status": "CERTIFIED_RESEARCH",
                "production_execution_authority": False,
            },
        },
    }


def test_manifest_is_deterministic_and_cannot_gain_execution_authority():
    payload = build_evidence_manifest(
        _g8_snapshot(),
        source_sha="deadbeef",
        evidence_epochs={"BTCUSDT": "epoch-17", "SOLUSDT": "epoch-8"},
    )
    assert payload["kind"] == "g9_stable_trading_evidence"
    assert payload["research_only"] is True
    assert payload["production_execution_authority"] is False
    assert payload["authority"]["execution"] == "none"
    assert payload["source_sha"] == "deadbeef"
    assert payload["parent_snapshot_hash"] == "a" * 64
    assert payload["symbols"]["SOLUSDT"]["profile_hash"] == "sol-profile"
    assert payload["system_contract_version"] == SYSTEM_CONTRACT_VERSION
    assert payload["plane"] == "STABLE_EVIDENCE"
    assert payload["authority_level"] == "STABLE_EVIDENCE"
    assert payload["manifest_hash"] == compute_manifest_hash(payload)
    assert validate_evidence_manifest(payload) == []
    assert payload == build_evidence_manifest(
        _g8_snapshot(),
        source_sha="deadbeef",
        evidence_epochs={"BTCUSDT": "epoch-17", "SOLUSDT": "epoch-8"},
    )


def test_manifest_validator_rejects_contract_metadata_tampering():
    payload = build_evidence_manifest(
        _g8_snapshot(),
        source_sha="deadbeef",
        evidence_epochs={"BTCUSDT": "epoch-17", "SOLUSDT": "epoch-8"},
    )
    payload["plane"] = "LIVE_CONTEXT"
    payload["manifest_hash"] = compute_manifest_hash(payload)
    assert "plane-invalid" in validate_evidence_manifest(payload)
