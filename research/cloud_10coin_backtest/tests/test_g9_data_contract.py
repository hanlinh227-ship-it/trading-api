from datetime import datetime, timedelta, timezone

import pytest

from g9.data_contract import build_envelope, validate_envelope


def base_envelope():
    ts = datetime(2026, 9, 13, 17, 30, tzinfo=timezone.utc)
    return build_envelope(
        kind="market_minute",
        source="crypto-research-gateway",
        source_sha="abc123",
        event_time=ts,
        ingest_time=ts + timedelta(milliseconds=250),
        freshness="FRESH",
        payload={"symbol": "BTCUSDT", "last": 77000.0},
        provenance={"price": {"provider": "bybit", "source_timestamp_ms": 1}},
    )


def test_canonical_envelope_is_research_only_and_hash_verified():
    payload = base_envelope()
    assert payload["contract_version"] == 1
    assert payload["authority"]["scope"] == "research_evidence"
    assert payload["authority"]["execution"] == "none"
    assert payload["production_execution_authority"] is False
    assert validate_envelope(payload) == []


def test_tampered_payload_is_rejected():
    payload = base_envelope()
    payload["payload"]["last"] = 1.0
    assert "PAYLOAD_HASH_MISMATCH" in validate_envelope(payload)


def test_execution_authority_escalation_is_rejected():
    payload = base_envelope()
    payload["authority"]["execution"] = "trade"
    payload["production_execution_authority"] = True
    errors = validate_envelope(payload)
    assert "EXECUTION_AUTHORITY_FORBIDDEN" in errors
    assert "PRODUCTION_EXECUTION_AUTHORITY_FORBIDDEN" in errors


def test_future_event_time_is_rejected():
    payload = base_envelope()
    payload["event_time"] = "2026-09-13T17:31:00+00:00"
    payload["ingest_time"] = "2026-09-13T17:30:00+00:00"
    assert "EVENT_AFTER_INGEST" in validate_envelope(payload)


def test_unknown_freshness_is_rejected():
    payload = base_envelope()
    payload["freshness"] = "MAYBE"
    assert "FRESHNESS_INVALID" in validate_envelope(payload)
