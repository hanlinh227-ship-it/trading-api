from datetime import datetime, timezone

import pytest

from g9.data_contract import build_envelope, validate_envelope
from g9_runtime.provider_gateway import GatewayMinuteProvider


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http-{self.status_code}")

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, bodies):
        self.bodies = list(bodies)

    def post(self, *_args, **_kwargs):
        if not self.bodies:
            raise AssertionError("unexpected extra request")
        return FakeResponse(self.bodies.pop(0))


def gateway_body(*, conflict=False, tamper=False):
    raw = {
        "ok": True,
        "degraded": False,
        "capability": "market_snapshot",
        "providers": ["bybit", "okx"],
        "observations": [
            {"provider": "bybit", "venue": "bybit", "symbol": "BTCUSDT", "instrumentType": "perpetual", "quoteCurrency": "USDT", "priceSemantic": "bid", "price": 77000.0, "sourceTimestampMs": 1789311000000, "receivedTimestampMs": 1789311000100},
            {"provider": "bybit", "venue": "bybit", "symbol": "BTCUSDT", "instrumentType": "perpetual", "quoteCurrency": "USDT", "priceSemantic": "ask", "price": 77000.2, "sourceTimestampMs": 1789311000000, "receivedTimestampMs": 1789311000100},
            {"provider": "bybit", "venue": "bybit", "symbol": "BTCUSDT", "instrumentType": "perpetual", "quoteCurrency": "USDT", "priceSemantic": "last", "price": 77000.1, "sourceTimestampMs": 1789311000000, "receivedTimestampMs": 1789311000100},
            {"provider": "okx", "venue": "okx", "symbol": "BTCUSDT", "instrumentType": "perpetual", "quoteCurrency": "USDT", "priceSemantic": "last", "price": 77000.15, "sourceTimestampMs": 1789311000000, "receivedTimestampMs": 1789311000150},
        ],
        "conflict": conflict,
        "resolutions": [],
        "failures": [],
    }
    contract = build_envelope(
        kind="crypto_market_research",
        source="crypto-research-gateway",
        source_sha="gateway-sha",
        event_time="2026-09-13T17:30:00+00:00",
        ingest_time="2026-09-13T17:30:00.250000+00:00",
        freshness="FRESH",
        payload=raw,
        provenance={"providers": ["bybit", "okx"]},
    )
    if tamper:
        contract["payload_hash"] = "0" * 64
    return {**raw, "dataContract": contract}


def test_gateway_minute_provider_validates_contract_and_never_averages_sources():
    provider = GatewayMinuteProvider(
        symbols=["BTCUSDT"],
        source_sha="g9-sha",
        base_url="https://gateway.example",
        session=FakeSession([gateway_body()]),
    )
    now = datetime(2026, 9, 13, 17, 30, 1, tzinfo=timezone.utc)
    payload = provider.fetch_minute_state(now)
    assert payload["provider"] == "CRYPTO_RESEARCH_GATEWAY"
    assert payload["symbols"]["BTCUSDT"]["market"]["bid"] == 77000.0
    assert payload["symbols"]["BTCUSDT"]["market"]["ask"] == 77000.2
    assert payload["symbols"]["BTCUSDT"]["market"]["last"] == 77000.1
    assert payload["symbols"]["BTCUSDT"]["market"]["regime"] == "UNKNOWN"
    assert validate_envelope(payload["data_contract"]) == []


def test_gateway_conflict_fails_closed():
    provider = GatewayMinuteProvider(
        symbols=["BTCUSDT"], source_sha="g9-sha", base_url="https://gateway.example", session=FakeSession([gateway_body(conflict=True)])
    )
    with pytest.raises(RuntimeError, match="gateway-price-conflict"):
        provider.fetch_minute_state(datetime(2026, 9, 13, 17, 30, 1, tzinfo=timezone.utc))


def test_invalid_gateway_contract_is_rejected_before_market_use():
    provider = GatewayMinuteProvider(
        symbols=["BTCUSDT"], source_sha="g9-sha", base_url="https://gateway.example", session=FakeSession([gateway_body(tamper=True)])
    )
    with pytest.raises(RuntimeError, match="gateway-data-contract-invalid"):
        provider.fetch_minute_state(datetime(2026, 9, 13, 17, 30, 1, tzinfo=timezone.utc))
