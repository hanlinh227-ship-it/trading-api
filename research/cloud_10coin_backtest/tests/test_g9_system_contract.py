from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from g9.system_contract import (
    AuthorityLevel,
    DataPlane,
    EvidenceEnvelope,
    Freshness,
    resolve_conflict,
    validate_envelope,
)


def _time(minute: int = 0) -> datetime:
    return datetime(2026, 9, 13, 16, minute, tzinfo=timezone.utc)


def _envelope(*, value: object, authority: AuthorityLevel, source: str = "railway", minute: int = 0):
    return EvidenceEnvelope.build(
        kind="market.regime",
        subject="BTCUSDT",
        value=value,
        source=source,
        source_sha="a" * 40,
        plane=DataPlane.LIVE_CONTEXT,
        authority=authority,
        freshness=Freshness.FRESH,
        event_time=_time(minute),
        ingest_time=_time(minute) + timedelta(seconds=1),
        research_only=True,
        production_execution_authority=False,
    )


def test_envelope_hash_is_stable_and_authority_cannot_escalate():
    first = _envelope(value="TREND_UP", authority=AuthorityLevel.LIVE_CONTEXT)
    second = _envelope(value="TREND_UP", authority=AuthorityLevel.LIVE_CONTEXT)
    assert first.envelope_hash == second.envelope_hash
    assert validate_envelope(first.to_dict()) == []

    tampered = first.to_dict()
    tampered["production_execution_authority"] = True
    errors = validate_envelope(tampered)
    assert "PRODUCTION_EXECUTION_AUTHORITY_FORBIDDEN" in errors


def test_higher_authority_wins_without_silent_averaging():
    lower = _envelope(value="LONG", authority=AuthorityLevel.EXPERIMENTAL)
    higher = _envelope(value="NO_TRADE", authority=AuthorityLevel.STABLE_EVIDENCE, source="github-brain")
    result = resolve_conflict([lower, higher])
    assert result.status == "RESOLVED"
    assert result.selected is higher
    assert result.reason == "HIGHER_AUTHORITY"


def test_equal_authority_material_conflict_blocks():
    a = _envelope(value="LONG", authority=AuthorityLevel.RESEARCH_CHAMPION, source="lane-a")
    b = _envelope(value="SHORT", authority=AuthorityLevel.RESEARCH_CHAMPION, source="lane-b")
    result = resolve_conflict([a, b])
    assert result.status == "BLOCKED"
    assert result.selected is None
    assert result.reason == "UNRESOLVED_EQUAL_AUTHORITY_CONFLICT"


def test_stale_live_context_cannot_override_fresh_stable_evidence():
    stale = EvidenceEnvelope.build(
        kind="entry.bias",
        subject="ETHUSDT",
        value="LONG",
        source="railway",
        source_sha="b" * 40,
        plane=DataPlane.LIVE_CONTEXT,
        authority=AuthorityLevel.LIVE_CONTEXT,
        freshness=Freshness.STALE,
        event_time=_time(0),
        ingest_time=_time(3),
        research_only=True,
        production_execution_authority=False,
    )
    stable = EvidenceEnvelope.build(
        kind="entry.bias",
        subject="ETHUSDT",
        value="NO_TRADE",
        source="github-brain",
        source_sha="c" * 40,
        plane=DataPlane.STABLE_EVIDENCE,
        authority=AuthorityLevel.STABLE_EVIDENCE,
        freshness=Freshness.FRESH,
        event_time=_time(3),
        ingest_time=_time(3),
        research_only=True,
        production_execution_authority=False,
    )
    result = resolve_conflict([stale, stable])
    assert result.status == "RESOLVED"
    assert result.selected is stable


def test_invalid_timestamp_order_is_rejected():
    with pytest.raises(ValueError, match="ingest_time"):
        EvidenceEnvelope.build(
            kind="market.price",
            subject="BTCUSDT",
            value=77000.0,
            source="railway",
            source_sha="d" * 40,
            plane=DataPlane.LIVE_CONTEXT,
            authority=AuthorityLevel.LIVE_CONTEXT,
            freshness=Freshness.FRESH,
            event_time=_time(2),
            ingest_time=_time(1),
            research_only=True,
            production_execution_authority=False,
        )
