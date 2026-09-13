from g9.data_contract import validate_envelope
from g9.manifest import build_evidence_manifest, compute_manifest_hash


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
    assert payload["manifest_hash"] == compute_manifest_hash(payload)
    assert validate_envelope(payload["data_contract"]) == []
    assert payload["data_contract"]["payload"] == {key: value for key, value in payload.items() if key != "data_contract"}
    assert payload == build_evidence_manifest(
        _g8_snapshot(),
        source_sha="deadbeef",
        evidence_epochs={"BTCUSDT": "epoch-17", "SOLUSDT": "epoch-8"},
    )
