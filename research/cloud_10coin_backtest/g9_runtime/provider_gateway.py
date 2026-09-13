from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import requests

from g9.contracts import EntryContextSnapshot, MarketStateSnapshot
from g9.data_contract import build_envelope, validate_envelope
from g9.market_state import build_market_state


class GatewayMinuteProvider:
    """Minute provider backed by the canonical read-only research gateway.

    The gateway already owns provider routing and price-conflict detection. This
    adapter never majority-votes or averages venue prices. It deterministically
    selects the first healthy provider chosen by the gateway router, validates the
    gateway data contract, and fails closed on material conflict.
    """

    def __init__(
        self,
        *,
        symbols: Iterable[str],
        source_sha: str,
        base_url: str,
        session: requests.Session | Any | None = None,
        timeout_seconds: float = 8.0,
        history_size: int = 120,
    ):
        normalized = tuple(str(symbol).upper() for symbol in symbols)
        if not normalized or len(set(normalized)) != len(normalized):
            raise ValueError("symbols must be non-empty and unique")
        self.symbols = normalized
        self.source_sha = str(source_sha)
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = float(timeout_seconds)
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=max(3, int(history_size))))

    @staticmethod
    def _to_dt_ms(value: Any) -> datetime:
        return datetime.fromtimestamp(float(value) / 1_000.0, tz=timezone.utc)

    def _request_snapshot(self, symbol: str) -> dict[str, Any]:
        response = self.session.post(
            self.base_url + "/research/market",
            json={"action": "snapshot", "symbol": symbol, "instrument": "perpetual"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("gateway-response-invalid")
        contract = body.get("dataContract")
        if not isinstance(contract, Mapping):
            raise RuntimeError("gateway-data-contract-missing")
        errors = validate_envelope(contract)
        if errors:
            raise RuntimeError("gateway-data-contract-invalid:" + ",".join(errors))
        if contract.get("payload") != {key: value for key, value in body.items() if key != "dataContract"}:
            raise RuntimeError("gateway-contract-payload-mismatch")
        if body.get("ok") is not True:
            raise RuntimeError(f"gateway-unavailable:{body.get('error', 'unknown')}")
        if body.get("conflict") is True:
            raise RuntimeError("gateway-price-conflict")
        return body

    @staticmethod
    def _select_provider(body: Mapping[str, Any]) -> str:
        providers = body.get("providers")
        if not isinstance(providers, list) or not providers:
            raise RuntimeError("gateway-provider-list-missing")
        return str(providers[0])

    @staticmethod
    def _selected_observations(body: Mapping[str, Any], provider: str) -> dict[str, Mapping[str, Any]]:
        observations = body.get("observations")
        if not isinstance(observations, list):
            raise RuntimeError("gateway-observations-missing")
        selected: dict[str, Mapping[str, Any]] = {}
        for item in observations:
            if not isinstance(item, Mapping) or str(item.get("provider")) != provider:
                continue
            semantic = str(item.get("priceSemantic") or "")
            if semantic in {"bid", "ask", "last", "mark", "index"} and semantic not in selected:
                selected[semantic] = item
        for required in ("bid", "ask", "last"):
            if required not in selected:
                raise RuntimeError(f"gateway-required-semantic-missing:{required}")
        return selected

    def _append_quote_bar(self, symbol: str, now: datetime, last: float) -> list[dict[str, Any]]:
        minute = now.replace(second=0, microsecond=0)
        history = self._history[symbol]
        if history and history[-1]["event_time"] == minute:
            row = history[-1]
            row["high"] = max(float(row["high"]), last)
            row["low"] = min(float(row["low"]), last)
            row["close"] = last
        else:
            history.append({
                "event_time": minute,
                "open": last,
                "high": last,
                "low": last,
                "close": last,
                "volume": 0.0,
            })
        return list(history)

    @staticmethod
    def _unknown_market(*, symbol: str, now: datetime, quote_time: datetime, bid: float, ask: float, last: float, provider: str) -> MarketStateSnapshot:
        age_ms = max(0, int((now - quote_time).total_seconds() * 1_000))
        return MarketStateSnapshot(
            symbol=symbol,
            venue=provider.upper(),
            instrument="PERPETUAL",
            event_time=now,
            ingest_time=now,
            quote_age_ms=age_ms,
            bid=bid,
            ask=ask,
            last=last,
            regime="UNKNOWN",
            regime_confidence=0.0,
            transition_probability=1.0,
            structure="UNKNOWN",
            volatility=0.0,
            directional_efficiency=0.0,
            uncertainty=1.0,
            provenance={"price": {"source": provider, "event_time": quote_time.isoformat()}},
        )

    def fetch_minute_state(self, now: datetime) -> dict[str, Any]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        staged: dict[str, dict[str, Any]] = {}
        gateway_contracts: dict[str, dict[str, Any]] = {}
        for symbol in self.symbols:
            body = self._request_snapshot(symbol)
            provider = self._select_provider(body)
            selected = self._selected_observations(body, provider)
            bid = float(selected["bid"]["price"])
            ask = float(selected["ask"]["price"])
            last = float(selected["last"]["price"])
            quote_time = self._to_dt_ms(selected["last"]["sourceTimestampMs"])
            bars = self._append_quote_bar(symbol, now, last)
            if len(bars) >= 3:
                market = build_market_state(
                    symbol=symbol,
                    venue=provider.upper(),
                    instrument="PERPETUAL",
                    bars=bars,
                    event_time=now,
                    ingest_time=now,
                    bid=bid,
                    ask=ask,
                    last=last,
                    quote_event_time=quote_time,
                )
            else:
                market = self._unknown_market(
                    symbol=symbol,
                    now=now,
                    quote_time=quote_time,
                    bid=bid,
                    ask=ask,
                    last=last,
                    provider=provider,
                )
            staged[symbol] = {"market": market, "provider": provider}
            gateway_contracts[symbol] = dict(body["dataContract"])

        def regime_score(regime: str) -> float:
            return 1.0 if regime == "TREND_UP" else -1.0 if regime == "TREND_DOWN" else 0.0

        anchors = [
            regime_score(staged[symbol]["market"].regime)
            for symbol in ("BTCUSDT", "ETHUSDT")
            if symbol in staged and staged[symbol]["market"].regime != "UNKNOWN"
        ]
        cross_asset_score = None if len(anchors) < 2 else sum(anchors) / len(anchors)

        symbols_payload: dict[str, dict[str, Any]] = {}
        freshness_values: list[str] = []
        for symbol, data in staged.items():
            market = data["market"]
            market_payload = market.to_dict()
            freshness_values.append(str(market_payload["freshness"]))
            entry = EntryContextSnapshot(
                symbol=symbol,
                event_time=now,
                market_snapshot_id=market_payload["snapshot_id"],
                funding=None,
                open_interest_delta=None,
                taker_imbalance=None,
                cross_asset_score=cross_asset_score,
                mark_index_premium=None,
                live_quality_score=float(market.regime_confidence),
                model_confidence=None,
                historical_oos_win_rate=None,
                uncertainty=float(market.uncertainty),
            )
            symbols_payload[symbol] = {"market": market_payload, "entry": entry.to_dict()}

        overall_freshness = "FRESH"
        if any(value == "STALE" for value in freshness_values):
            overall_freshness = "STALE"
        elif any(value == "DEGRADED" for value in freshness_values):
            overall_freshness = "DEGRADED"

        payload = {
            "schema_version": 1,
            "kind": "g9_minute_intelligence",
            "event_time": now.isoformat(),
            "provider": "CRYPTO_RESEARCH_GATEWAY",
            "symbols": symbols_payload,
            "research_only": True,
            "production_execution_authority": False,
        }
        payload["data_contract"] = build_envelope(
            kind="g9_minute_intelligence",
            source="g9-minute-runtime",
            source_sha=self.source_sha,
            event_time=now,
            ingest_time=now,
            freshness=overall_freshness,
            payload={key: value for key, value in payload.items() if key != "data_contract"},
            provenance={
                "gateway_contracts": {
                    symbol: {
                        "source": contract.get("source"),
                        "source_sha": contract.get("source_sha"),
                        "payload_hash": contract.get("payload_hash"),
                    }
                    for symbol, contract in gateway_contracts.items()
                }
            },
        )
        return payload
