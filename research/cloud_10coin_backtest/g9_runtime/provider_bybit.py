from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from g9.contracts import EntryContextSnapshot
from g9.market_state import build_market_state


class BybitPublicMinuteProvider:
    """Read-only Bybit linear public-market provider. No credentials are accepted."""

    def __init__(
        self,
        *,
        symbols: Iterable[str],
        session: requests.Session | Any | None = None,
        base_url: str = "https://api.bybit.com",
        timeout_seconds: float = 5.0,
    ):
        normalized = [str(symbol).upper() for symbol in symbols]
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("symbols must be non-empty and unique")
        self.symbols = tuple(normalized)
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self._previous_open_interest: dict[str, float] = {}

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            self.base_url + path,
            params=params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid Bybit public response")
        if int(payload.get("retCode", -1)) != 0:
            raise RuntimeError(f"Bybit public API error: {payload.get('retCode')}:{payload.get('retMsg')}")
        return payload

    @staticmethod
    def _to_dt_ms(value: int | float | str) -> datetime:
        return datetime.fromtimestamp(float(value) / 1_000.0, tz=timezone.utc)

    @staticmethod
    def _ticker_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            raise ValueError("invalid Bybit ticker result")
        return {
            str(row["symbol"]).upper(): dict(row)
            for row in rows
            if isinstance(row, dict) and row.get("symbol")
        }

    @staticmethod
    def _closed_bars(payload: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            raise ValueError("invalid Bybit kline result")
        now_ms = int(now.timestamp() * 1_000)
        parsed: list[dict[str, Any]] = []
        for raw in rows:
            if not isinstance(raw, list) or len(raw) < 6:
                continue
            open_ms = int(raw[0])
            close_ms = open_ms + 60_000 - 1
            if close_ms > now_ms:
                continue
            parsed.append(
                {
                    "event_time": BybitPublicMinuteProvider._to_dt_ms(close_ms),
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": float(raw[5]),
                }
            )
        parsed.sort(key=lambda row: row["event_time"])
        return parsed

    @staticmethod
    def _regime_score(regime: str) -> float:
        if regime == "TREND_UP":
            return 1.0
        if regime == "TREND_DOWN":
            return -1.0
        return 0.0

    def fetch_minute_state(self, now: datetime) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        tickers_payload = self._get_json("/v5/market/tickers", params={"category": "linear"})
        tickers = self._ticker_index(tickers_payload)
        quote_time = self._to_dt_ms(tickers_payload.get("time", int(now.timestamp() * 1_000)))

        staged: dict[str, dict[str, Any]] = {}
        for symbol in self.symbols:
            ticker = tickers.get(symbol)
            if ticker is None:
                raise ValueError(f"missing Bybit public state for {symbol}")
            kline_payload = self._get_json(
                "/v5/market/kline",
                params={
                    "category": "linear",
                    "symbol": symbol,
                    "interval": "1",
                    "limit": 60,
                },
            )
            bars = self._closed_bars(kline_payload, now)
            market = build_market_state(
                symbol=symbol,
                venue="BYBIT",
                instrument="LINEAR_PERPETUAL",
                bars=bars,
                event_time=now,
                ingest_time=now,
                bid=float(ticker["bid1Price"]),
                ask=float(ticker["ask1Price"]),
                last=float(ticker["lastPrice"]),
                quote_event_time=quote_time,
            )

            current_oi = float(ticker.get("openInterest") or 0.0)
            previous_oi = self._previous_open_interest.get(symbol)
            oi_delta = None
            if previous_oi not in (None, 0.0):
                oi_delta = round((current_oi - previous_oi) / previous_oi, 8)
            self._previous_open_interest[symbol] = current_oi

            mark_price = float(ticker["markPrice"])
            index_price = float(ticker["indexPrice"])
            premium = None if index_price == 0 else (mark_price - index_price) / index_price
            funding_raw = ticker.get("fundingRate")
            staged[symbol] = {
                "market_obj": market,
                "funding": None if funding_raw in (None, "") else float(funding_raw),
                "open_interest_delta": oi_delta,
                "mark_index_premium": premium,
            }

        context_sources = [
            self._regime_score(staged[symbol]["market_obj"].regime)
            for symbol in ("BTCUSDT", "ETHUSDT")
            if symbol in staged
        ]
        cross_asset_score = None
        if len(context_sources) == 2:
            cross_asset_score = sum(context_sources) / 2.0

        symbols_payload: dict[str, dict[str, Any]] = {}
        for symbol, data in staged.items():
            market = data["market_obj"]
            entry = EntryContextSnapshot(
                symbol=symbol,
                event_time=now,
                market_snapshot_id=market.to_dict()["snapshot_id"],
                funding=data["funding"],
                open_interest_delta=data["open_interest_delta"],
                taker_imbalance=None,
                cross_asset_score=cross_asset_score,
                mark_index_premium=data["mark_index_premium"],
                live_quality_score=float(market.regime_confidence),
                model_confidence=None,
                historical_oos_win_rate=None,
                uncertainty=float(market.uncertainty),
            )
            symbols_payload[symbol] = {
                "market": market.to_dict(),
                "entry": entry.to_dict(),
            }

        return {
            "schema_version": 1,
            "kind": "g9_minute_intelligence",
            "event_time": now.isoformat(),
            "provider": "BYBIT_PUBLIC_LINEAR",
            "symbols": symbols_payload,
            "research_only": True,
            "production_execution_authority": False,
        }
