from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from g9.contracts import EntryContextSnapshot
from g9.market_state import build_market_state


class BinancePublicMinuteProvider:
    """Read-only Binance USD-M public-market provider. No credentials are accepted."""

    def __init__(
        self,
        *,
        symbols: Iterable[str],
        session: requests.Session | Any | None = None,
        base_url: str = "https://fapi.binance.com",
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

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(
            self.base_url + path,
            params=params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _index_by_symbol(payload: Any) -> dict[str, dict[str, Any]]:
        if isinstance(payload, dict):
            payload = [payload]
        return {
            str(row["symbol"]).upper(): dict(row)
            for row in payload
            if isinstance(row, dict) and row.get("symbol")
        }

    @staticmethod
    def _to_dt_ms(value: int | float | str) -> datetime:
        return datetime.fromtimestamp(float(value) / 1_000.0, tz=timezone.utc)

    @staticmethod
    def _parse_closed_bars(payload: Any, now: datetime) -> tuple[list[dict[str, Any]], float | None]:
        now_ms = int(now.timestamp() * 1_000)
        rows: list[dict[str, Any]] = []
        total_volume = 0.0
        total_taker_buy = 0.0
        for raw in payload:
            if len(raw) < 10:
                continue
            close_ms = int(raw[6])
            if close_ms > now_ms:
                continue
            volume = float(raw[5])
            taker_buy = float(raw[9])
            rows.append(
                {
                    "event_time": BinancePublicMinuteProvider._to_dt_ms(close_ms),
                    "open": float(raw[1]),
                    "high": float(raw[2]),
                    "low": float(raw[3]),
                    "close": float(raw[4]),
                    "volume": volume,
                }
            )
            total_volume += volume
            total_taker_buy += taker_buy
        imbalance = None
        if total_volume > 0:
            imbalance = round((2.0 * total_taker_buy / total_volume) - 1.0, 8)
        return rows, imbalance

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

        books = self._index_by_symbol(self._get_json("/fapi/v1/ticker/bookTicker"))
        premiums = self._index_by_symbol(self._get_json("/fapi/v1/premiumIndex"))

        staged: dict[str, dict[str, Any]] = {}
        for symbol in self.symbols:
            if symbol not in books or symbol not in premiums:
                raise ValueError(f"missing Binance public state for {symbol}")
            book = books[symbol]
            premium = premiums[symbol]
            klines = self._get_json(
                "/fapi/v1/klines",
                params={"symbol": symbol, "interval": "1m", "limit": 60},
            )
            oi_payload = self._get_json(
                "/fapi/v1/openInterest",
                params={"symbol": symbol},
            )
            bars, taker_imbalance = self._parse_closed_bars(klines, now)
            quote_time = self._to_dt_ms(book.get("time", int(now.timestamp() * 1_000)))
            market = build_market_state(
                symbol=symbol,
                venue="BINANCE",
                instrument="USD_M_PERPETUAL",
                bars=bars,
                event_time=now,
                ingest_time=now,
                bid=float(book["bidPrice"]),
                ask=float(book["askPrice"]),
                last=(float(book["bidPrice"]) + float(book["askPrice"])) / 2.0,
                quote_event_time=quote_time,
            )

            current_oi = float(oi_payload["openInterest"])
            previous_oi = self._previous_open_interest.get(symbol)
            oi_delta = None
            if previous_oi not in (None, 0.0):
                oi_delta = round((current_oi - previous_oi) / previous_oi, 8)
            self._previous_open_interest[symbol] = current_oi

            mark_price = float(premium["markPrice"])
            index_price = float(premium["indexPrice"])
            mark_index_premium = None if index_price == 0 else (mark_price - index_price) / index_price

            staged[symbol] = {
                "market_obj": market,
                "funding": float(premium.get("lastFundingRate", 0.0)),
                "open_interest_delta": oi_delta,
                "taker_imbalance": taker_imbalance,
                "mark_index_premium": mark_index_premium,
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
                taker_imbalance=data["taker_imbalance"],
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
            "provider": "BINANCE_PUBLIC_USD_M",
            "symbols": symbols_payload,
            "research_only": True,
            "production_execution_authority": False,
        }
