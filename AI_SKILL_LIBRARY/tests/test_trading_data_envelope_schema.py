import json
from pathlib import Path

from research.cloud_10coin_backtest.g9.data_contract import (
    ALLOWED_FRESHNESS,
    AUTHORITY_SCOPE,
    CONTRACT_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "v4/schemas/trading_data_envelope.schema.json"


def test_canonical_trading_data_envelope_schema_matches_runtime_contract():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    props = schema["properties"]
    assert props["contract_version"]["const"] == CONTRACT_VERSION
    assert set(props["freshness"]["enum"]) == ALLOWED_FRESHNESS
    assert props["authority"]["properties"]["scope"]["const"] == AUTHORITY_SCOPE
    assert props["authority"]["properties"]["execution"]["const"] == "none"
    assert props["research_only"]["const"] is True
    assert props["production_execution_authority"]["const"] is False
    assert props["payload_hash"]["pattern"] == "^[0-9a-f]{64}$"


def test_schema_requires_all_boundary_integrity_fields():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert set(schema["required"]) == {
        "contract_version",
        "kind",
        "source",
        "source_sha",
        "event_time",
        "ingest_time",
        "freshness",
        "authority",
        "research_only",
        "production_execution_authority",
        "provenance",
        "payload",
        "payload_hash",
    }
