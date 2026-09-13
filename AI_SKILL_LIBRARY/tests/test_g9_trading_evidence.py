from AI_SKILL_LIBRARY.v4.tools.validate_g9_trading_evidence import validate_manifest, validate_snapshot


def _valid_payload():
    from research.cloud_10coin_backtest.g9.manifest import build_evidence_manifest

    g8 = {
        "schema_version": 1,
        "kind": "g8_trading_research_evidence",
        "research_only": True,
        "authority": {"execution": "none", "production_strategy": "BYBIT-BTC-STATEFLOW-2.1"},
        "source_sha": "base",
        "data_cutoff": "2026-09-12",
        "snapshot_hash": "a" * 64,
        "symbols": {
            "BTCUSDT": {
                "profile_hash": "profile-1",
                "status": "RESEARCH_ONLY",
                "production_execution_authority": False,
            }
        },
    }
    return build_evidence_manifest(g8, source_sha="deadbeef", evidence_epochs={"BTCUSDT": "epoch-1"})


def test_validator_accepts_research_only_manifest():
    payload = _valid_payload()
    assert validate_snapshot(payload) == []
    assert validate_manifest(payload) == []


def test_validator_rejects_any_execution_authority_escalation():
    payload = _valid_payload()
    payload["production_execution_authority"] = True
    errors = validate_snapshot(payload)
    assert "production-execution-authority-forbidden" in errors


def test_validator_rejects_tampered_manifest_hash():
    payload = _valid_payload()
    payload["symbols"]["BTCUSDT"]["profile_hash"] = "tampered"
    assert "manifest-hash-mismatch" in validate_snapshot(payload)


def test_validator_rejects_tampered_canonical_data_contract():
    payload = _valid_payload()
    payload["data_contract"]["payload_hash"] = "0" * 64
    assert "data-contract:payload-hash-mismatch" in validate_snapshot(payload)


def test_validator_rejects_data_contract_authority_escalation():
    payload = _valid_payload()
    payload["data_contract"]["authority"]["execution"] = "trade"
    assert "data-contract:execution-authority-forbidden" in validate_snapshot(payload)
