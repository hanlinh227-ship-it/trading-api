from datetime import datetime, timedelta, timezone

import pytest

from g9_runtime.provider_binance import BinancePublicMinuteProvider
from g9_runtime.provider_bybit import BybitPublicMinuteProvider
from g9_runtime.provider_chain import FailoverMinuteProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, now_ms):
        self.now_ms = now_ms
        self.open_interest = 1000.0
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if url.endswith("/fapi/v1/ticker/bookTicker"):
            return FakeResponse([
                {"symbol": "BTCUSDT", "bidPrice": "102.59", "askPrice": "102.61", "time": self.now_ms - 250}
            ])
        if url.endswith("/fapi/v1/premiumIndex"):
            return FakeResponse([
                {
                    "symbol": "BTCUSDT",
                    "markPrice": "102.60",
                    "indexPrice": "102.50",
                    "lastFundingRate": "0.0001",
                    "time": self.now_ms - 100,
                }
            ])
        if url.endswith("/fapi/v1/klines"):
            start = self.now_ms - 6 * 60_000
            rows = []
            for i, close in enumerate([100.0, 100.4, 100.8, 101.3, 101.9, 102.6]):
                open_ms = start + i * 60_000
                close_ms = open_ms + 59_999
                rows.append([
                    open_ms,
                    str(close - 0.2),
                    str(close + 0.3),
                    str(close - 0.4),
                    str(close),
                    "100",
                    close_ms,
                    "0",
                    100,
                    "60",
                    "0",
                    "0",
                ])
            return FakeResponse(rows)
        if url.endswith("/fapi/v1/openInterest"):
            return FakeResponse({"symbol": "BTCUSDT", "openInterest": str(self.open_interest), "time": self.now_ms})
        raise AssertionError(url)


def test_public_provider_builds_causal_market_and_derivatives_context_without_credentials():
    now = datetime(2026, 9, 13, 15, 10, tzinfo=timezone.utc)
    session = FakeSession(int(now.timestamp() * 1000))
    provider = BinancePublicMinuteProvider(symbols=["BTCUSDT"], session=session)

    first = provider.fetch_minute_state(now)
    row = first["symbols"]["BTCUSDT"]
    assert first["research_only"] is True
    assert first["production_execution_authority"] is False
    assert row["market"]["freshness"] == "FRESH"
    assert row["market"]["regime"] == "TREND_UP"
    assert row["entry"]["funding"] == 0.0001
    assert row["entry"]["taker_imbalance"] == 0.2
    assert row["entry"]["open_interest_delta"] == "UNKNOWN"
    assert row["entry"]["mark_index_premium"] > 0
    assert row["entry"]["model_confidence"] == "UNKNOWN"
    assert all(call[1] is None or "apiKey" not in call[1] for call in session.calls)

    session.open_interest = 1010.0
    second = provider.fetch_minute_state(now + timedelta(minutes=1))
    assert second["symbols"]["BTCUSDT"]["entry"]["open_interest_delta"] == 0.01


class FakeBybitSession:
    def __init__(self, now_ms):
        self.now_ms = now_ms
        self.oi = 2000.0
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if url.endswith("/v5/market/tickers"):
            return FakeResponse({
                "retCode": 0,
                "result": {"list": [{
                    "symbol": "BTCUSDT",
                    "bid1Price": "102.59",
                    "ask1Price": "102.61",
                    "lastPrice": "102.60",
                    "markPrice": "102.60",
                    "indexPrice": "102.50",
                    "fundingRate": "0.0001",
                    "openInterest": str(self.oi),
                }]},
                "time": self.now_ms - 100,
            })
        if url.endswith("/v5/market/kline"):
            start = self.now_ms - 6 * 60_000
            rows = []
            for i, close in enumerate([100.0, 100.4, 100.8, 101.3, 101.9, 102.6]):
                open_ms = start + i * 60_000
                rows.append([
                    str(open_ms), str(close - 0.2), str(close + 0.3),
                    str(close - 0.4), str(close), "100", "0"
                ])
            return FakeResponse({"retCode": 0, "result": {"list": list(reversed(rows))}, "time": self.now_ms})
        raise AssertionError(url)


def test_bybit_backup_provider_preserves_unknown_fields_instead_of_inventing_them():
    now = datetime(2026, 9, 13, 15, 10, tzinfo=timezone.utc)
    session = FakeBybitSession(int(now.timestamp() * 1000))
    provider = BybitPublicMinuteProvider(symbols=["BTCUSDT"], session=session)

    first = provider.fetch_minute_state(now)
    row = first["symbols"]["BTCUSDT"]
    assert first["provider"] == "BYBIT_PUBLIC_LINEAR"
    assert row["market"]["freshness"] == "FRESH"
    assert row["entry"]["funding"] == 0.0001
    assert row["entry"]["taker_imbalance"] == "UNKNOWN"
    assert row["entry"]["open_interest_delta"] == "UNKNOWN"
    assert row["entry"]["model_confidence"] == "UNKNOWN"

    session.oi = 2020.0
    second = provider.fetch_minute_state(now + timedelta(minutes=1))
    assert second["symbols"]["BTCUSDT"]["entry"]["open_interest_delta"] == 0.01


class DownProvider:
    def fetch_minute_state(self, now):
        raise RuntimeError("HTTP 451 geo-blocked")


class GoodProvider:
    def fetch_minute_state(self, now):
        return {
            "schema_version": 1,
            "kind": "g9_minute_intelligence",
            "event_time": now.isoformat(),
            "provider": "BYBIT_PUBLIC_LINEAR",
            "symbols": {"BTCUSDT": {"market": {"freshness": "FRESH"}, "entry": {"taker_imbalance": "UNKNOWN"}}},
            "research_only": True,
            "production_execution_authority": False,
        }


def test_provider_chain_degrades_locally_when_primary_is_geo_blocked():
    chain = FailoverMinuteProvider([
        ("BINANCE_PUBLIC_USD_M", DownProvider()),
        ("BYBIT_PUBLIC_LINEAR", GoodProvider()),
    ])
    now = datetime(2026, 9, 13, 15, 10, tzinfo=timezone.utc)
    payload = chain.fetch_minute_state(now)

    assert payload["provider"] == "BYBIT_PUBLIC_LINEAR"
    assert payload["provider_status"] == "DEGRADED_FAILOVER"
    assert payload["provider_failures"][0]["provider"] == "BINANCE_PUBLIC_USD_M"
    assert "451" in payload["provider_failures"][0]["error"]
    assert payload["production_execution_authority"] is False


def test_provider_chain_fails_closed_only_when_all_sources_fail():
    chain = FailoverMinuteProvider([
        ("binance", DownProvider()),
        ("backup", DownProvider()),
    ])
    with pytest.raises(RuntimeError, match="all minute providers failed"):
        chain.fetch_minute_state(datetime(2026, 9, 13, 15, 10, tzinfo=timezone.utc))
