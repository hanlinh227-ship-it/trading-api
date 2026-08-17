#!/usr/bin/env python3
"""Strict Twelve Data Grow55 client for supported non-crypto markets.

Design goals:
- never trust a shorthand ticker without an exact instrument mapping;
- use /quote (with last_quote_at) for the current aggregated price;
- hard-validate /time_series metadata before using candles;
- only use closed candles for technical calculations;
- return DATA_BLOCK for unsupported/ambiguous cash indices and futures;
- never fabricate bid/ask or an executable broker spread.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

VERSION = "V2-TWELVEDATA-DIRECT-STRICT"
BASE_URL = "https://api.twelvedata.com"

FOREX_CCY = {
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
    "SGD", "HKD", "NOK", "SEK", "DKK", "PLN", "CZK", "HUF",
    "MXN", "ZAR", "TRY", "CNH", "CNY",
}

# Exact Twelve Data commodity/metal catalog symbols verified on Grow55.
COMMODITY_ALIASES = {
    "XAUUSD": ("XAU/USD", "metal", "Precious Metal", "Gold Spot / US Dollar"),
    "GOLD": ("XAU/USD", "metal", "Precious Metal", "Gold Spot / US Dollar"),
    "XAGUSD": ("XAG/USD", "metal", "Precious Metal", "Silver Spot / US Dollar"),
    "SILVER": ("XAG/USD", "metal", "Precious Metal", "Silver Spot / US Dollar"),
    "XPTUSD": ("XPT/USD", "metal", "Industrial Metal", "Platinum Spot / US Dollar"),
    "XPDUSD": ("XPD/USD", "metal", "Industrial Metal", "Palladium Spot / US Dollar"),
    "WTIUSD": ("WTI/USD", "commodity_spot", "Energy Resource", "Crude Oil WTI Spot / US Dollar"),
    "WTI": ("WTI/USD", "commodity_spot", "Energy Resource", "Crude Oil WTI Spot / US Dollar"),
    "BRENTUSD": ("XBR/USD", "commodity_spot", "Energy Resource", "Brent Spot / US Dollar"),
    "BRENT": ("XBR/USD", "commodity_spot", "Energy Resource", "Brent Spot / US Dollar"),
}

# These aliases are intentionally blocked. Direct diagnostics on 2026-08-17
# proved that plain NDX/SPX resolve to unrelated listed securities, while the
# Grow55 /indices catalog exposed no US cash-index rows. Even canonical GDAXI
# catalog rows returned 404 on core endpoints with the current Grow plan.
CASH_INDEX_ALIASES = {
    "NDX": "Nasdaq-100 cash index",
    "NAS100": "Nasdaq-100 cash index",
    "NASDAQ100": "Nasdaq-100 cash index",
    "USTEC": "Nasdaq-100 cash index",
    "SPX": "S&P 500 cash index",
    "SP500": "S&P 500 cash index",
    "US500": "S&P 500 cash index",
    "SPX500": "S&P 500 cash index",
    "DJI": "Dow Jones Industrial Average cash index",
    "US30": "Dow Jones Industrial Average cash index",
    "DOW": "Dow Jones Industrial Average cash index",
    "N225": "Nikkei 225 cash index",
    "JP225": "Nikkei 225 cash index",
    "NIKKEI": "Nikkei 225 cash index",
    "NIKKEI225": "Nikkei 225 cash index",
    "DAX": "DAX cash index",
    "GDAXI": "DAX cash index",
    "DE40": "DAX cash index",
    "GER40": "DAX cash index",
    "FTSE": "FTSE 100 cash index",
    "UK100": "FTSE 100 cash index",
    "CAC": "CAC 40 cash index",
    "FR40": "CAC 40 cash index",
    "HSI": "Hang Seng cash index",
    "VIX": "CBOE Volatility Index",
    "RUT": "Russell 2000 cash index",
}

FUTURES_ALIASES = {
    "NQ": "E-mini Nasdaq-100 futures",
    "MNQ": "Micro E-mini Nasdaq-100 futures",
    "ES": "E-mini S&P 500 futures",
    "MES": "Micro E-mini S&P 500 futures",
    "GC": "COMEX Gold futures",
    "SI": "COMEX Silver futures",
    "CL": "NYMEX WTI Crude Oil futures",
}

FRAME_SPECS = {
    "D1": ("1day", 220, 70),
    "H4": ("4h", 220, 90),
    "H1": ("1h", 220, 110),
    "M15": ("15min", 220, 120),
    "M5": ("5min", 220, 120),
    "M1": ("1min", 80, 30),
}

INTERVAL_SECONDS = {
    "1min": 60,
    "5min": 300,
    "15min": 900,
    "30min": 1800,
    "45min": 2700,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "8h": 28800,
    "1day": 86400,
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def clean_symbol(value: str) -> str:
    return str(value).upper().replace("/", "").replace("-", "").replace("_", "").replace(":", "").replace(" ", "").strip()


def fnum(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except Exception:
        return None


def rnd(value, digits=8):
    if value is None:
        return None
    return round(float(value), digits)


def td_key() -> str:
    key = os.environ.get("TWELVEDATA_API_KEY") or ""
    if not key:
        raise RuntimeError("TWELVEDATA_API_KEY is missing")
    return key


def request_json(endpoint: str, params: dict | None = None, retries: int = 2, timeout: int = 35):
    query = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{BASE_URL}/{endpoint}" + (f"?{query}" if query else "")
    headers = {
        "Authorization": f"apikey {td_key()}",
        "Accept": "application/json",
        "User-Agent": "trading-api-twelvedata-strict/2.0",
    }
    last = None
    for attempt in range(retries + 1):
        started = time.time()
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                return {
                    "ok": True,
                    "httpStatus": response.status,
                    "data": data,
                    "latencyMs": int((time.time() - started) * 1000),
                    "fetchedAt": now_iso(),
                }
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except Exception:
                data = {"raw": raw[:1000]}
            last = {
                "ok": False,
                "httpStatus": e.code,
                "data": data,
                "latencyMs": int((time.time() - started) * 1000),
                "fetchedAt": now_iso(),
            }
            if e.code not in (429, 500, 502, 503, 504) or attempt >= retries:
                return last
        except Exception as e:
            last = {
                "ok": False,
                "httpStatus": None,
                "error": str(e),
                "latencyMs": int((time.time() - started) * 1000),
                "fetchedAt": now_iso(),
            }
            if attempt >= retries:
                return last
        time.sleep(1.25 * (attempt + 1))
    return last


def resolve_symbol(value: str) -> dict:
    requested = clean_symbol(value)
    if requested in FUTURES_ALIASES:
        return {
            "status": "DATA_BLOCK",
            "requestedSymbol": requested,
            "marketType": "future",
            "instrumentName": FUTURES_ALIASES[requested],
            "reason": "TWELVE_DATA_FUTURES_NOT_AVAILABLE",
            "message": "Grow55 catalog/search did not expose the exact CME/COMEX/NYMEX futures contract. A same-text ticker must not be substituted.",
        }
    if requested in CASH_INDEX_ALIASES:
        return {
            "status": "DATA_BLOCK",
            "requestedSymbol": requested,
            "marketType": "index",
            "instrumentName": CASH_INDEX_ALIASES[requested],
            "reason": "TWELVE_DATA_CASH_INDEX_NOT_USABLE_ON_GROW55",
            "message": "The exact cash index is not safely available through current Grow55 core endpoints. Ambiguous NDX/SPX/DAX tickers are forbidden.",
        }
    if requested in COMMODITY_ALIASES:
        market_symbol, market_type, expected_type, name = COMMODITY_ALIASES[requested]
        return {
            "status": "ok",
            "requestedSymbol": requested,
            "marketSymbol": market_symbol,
            "marketType": market_type,
            "expectedType": expected_type,
            "instrumentName": name,
        }
    if len(requested) == 6 and requested.isalpha():
        base, quote = requested[:3], requested[3:]
        if base in FOREX_CCY and quote in FOREX_CCY and base != quote:
            return {
                "status": "ok",
                "requestedSymbol": requested,
                "marketSymbol": f"{base}/{quote}",
                "marketType": "forex",
                "expectedType": "Physical Currency",
                "instrumentName": f"{base}/{quote}",
            }
    return {
        "status": "DATA_BLOCK",
        "requestedSymbol": requested,
        "marketType": "unknown",
        "reason": "SYMBOL_NOT_IN_STRICT_REGISTRY",
        "message": "Symbol is not in the strict Twelve Data registry. Add an explicit canonical mapping before use.",
    }


def meta_matches(meta: dict, resolved: dict) -> tuple[bool, str | None]:
    if not isinstance(meta, dict):
        return False, "MISSING_META"
    if str(meta.get("symbol", "")).upper() != resolved["marketSymbol"].upper():
        return False, f"META_SYMBOL_MISMATCH:{meta.get('symbol')}"
    expected_type = resolved.get("expectedType")
    if expected_type and meta.get("type") != expected_type:
        return False, f"META_TYPE_MISMATCH:{meta.get('type')}"
    return True, None


def parse_td_datetime(value: str) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def is_closed_bar(dt_value: str, interval: str, now: datetime | None = None) -> bool:
    opened = parse_td_datetime(dt_value)
    seconds = INTERVAL_SECONDS.get(interval)
    if opened is None or seconds is None:
        return True
    now = now or now_utc()
    return opened + timedelta(seconds=seconds) <= now


def ema(values, period):
    if len(values) < period:
        return None
    result = sum(values[:period]) / period
    k = 2 / (period + 1)
    for value in values[period:]:
        result = value * k + result * (1 - k)
    return result


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        gains += max(diff, 0)
        losses += max(-diff, 0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain, loss = max(diff, 0), max(-diff, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def atr(candles, period=14):
    if len(candles) <= period:
        return None
    trs = []
    for i in range(1, len(candles)):
        cur, prev = candles[i], candles[i - 1]
        trs.append(max(cur["high"] - cur["low"], abs(cur["high"] - prev["close"]), abs(cur["low"] - prev["close"])))
    result = sum(trs[:period]) / period
    for tr in trs[period:]:
        result = (result * (period - 1) + tr) / period
    return result


def technical_summary(candles):
    if len(candles) < 20:
        return None
    closes = [c["close"] for c in candles]
    latest = candles[-1]
    e20, e50, e200 = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    r14, a14 = rsi(closes), atr(candles)
    recent = candles[-50:]
    trend = "neutral"
    if e20 is not None and e50 is not None:
        if latest["close"] > e20 > e50:
            trend = "bullish"
        elif latest["close"] < e20 < e50:
            trend = "bearish"
    return {
        "close": rnd(latest["close"]),
        "ema20": rnd(e20),
        "ema50": rnd(e50),
        "ema200": rnd(e200),
        "rsi14": rnd(r14, 2),
        "atr14": rnd(a14),
        "recent50High": rnd(max(c["high"] for c in recent)),
        "recent50Low": rnd(min(c["low"] for c in recent)),
        "trend": trend,
    }


def fetch_frame(resolved: dict, key: str) -> dict:
    interval, fetch_size, return_size = FRAME_SPECS[key]
    result = request_json("time_series", {
        "symbol": resolved["marketSymbol"],
        "interval": interval,
        "outputsize": fetch_size,
        "timezone": "UTC",
        "order": "ASC",
    })
    if not result.get("ok"):
        data = result.get("data") or {}
        return {"status": "error", "interval": interval, "error": data.get("message") or result.get("error") or f"HTTP_{result.get('httpStatus')}"}
    data = result.get("data") or {}
    ok, reason = meta_matches(data.get("meta") or {}, resolved)
    if not ok:
        return {"status": "DATA_BLOCK", "interval": interval, "error": reason, "providerMeta": data.get("meta")}
    rows = data.get("values") or []
    candles = []
    for row in rows:
        o, h, l, c = fnum(row.get("open")), fnum(row.get("high")), fnum(row.get("low")), fnum(row.get("close"))
        if None in (o, h, l, c):
            continue
        if not is_closed_bar(row.get("datetime"), interval):
            continue
        candles.append({"datetime": row.get("datetime"), "open": o, "high": h, "low": l, "close": c, "volume": fnum(row.get("volume"))})
    candles.sort(key=lambda x: x["datetime"])
    if not candles:
        return {"status": "error", "interval": interval, "error": "NO_CLOSED_CANDLES", "providerMeta": data.get("meta")}
    latest = candles[-1]
    compact = [[c["datetime"], c["open"], c["high"], c["low"], c["close"], c.get("volume")] for c in candles[-return_size:]]
    return {
        "status": "ok",
        "interval": interval,
        "candleCount": len(candles),
        "latestCandle": latest,
        "summary": technical_summary(candles),
        "candles": compact,
        "providerMeta": data.get("meta"),
        "fetchedAt": result.get("fetchedAt"),
    }


def quote_age_ms(last_quote_at) -> int | None:
    try:
        ts = int(last_quote_at)
        return max(0, int((now_utc() - datetime.fromtimestamp(ts, timezone.utc)).total_seconds() * 1000))
    except Exception:
        return None


def fetch_quote(resolved: dict) -> dict:
    result = request_json("quote", {"symbol": resolved["marketSymbol"], "timezone": "UTC"})
    if not result.get("ok"):
        data = result.get("data") or {}
        return {"status": "error", "error": data.get("message") or result.get("error") or f"HTTP_{result.get('httpStatus')}", "fetchedAt": result.get("fetchedAt")}
    data = result.get("data") or {}
    if str(data.get("symbol", "")).upper() != resolved["marketSymbol"].upper():
        return {"status": "DATA_BLOCK", "error": f"QUOTE_SYMBOL_MISMATCH:{data.get('symbol')}", "raw": data}
    price = fnum(data.get("close"))
    if price is None:
        return {"status": "error", "error": "QUOTE_MISSING_CLOSE", "raw": data}
    age = quote_age_ms(data.get("last_quote_at"))
    return {
        "status": "ok",
        "symbol": data.get("symbol"),
        "name": data.get("name"),
        "exchange": data.get("exchange"),
        "micCode": data.get("mic_code"),
        "currency": data.get("currency"),
        "currentPrice": price,
        "priceType": "twelvedata_quote_close",
        "quoteTimestamp": data.get("last_quote_at"),
        "quoteTimestampISO": datetime.fromtimestamp(int(data["last_quote_at"]), timezone.utc).isoformat().replace("+00:00", "Z") if data.get("last_quote_at") else None,
        "quoteAgeMs": age,
        "quoteTimestampVerified": age is not None,
        "strictV74PriceFresh": age is not None and age <= 30000,
        "isMarketOpen": data.get("is_market_open"),
        "bid": None,
        "ask": None,
        "spreadVerified": False,
        "executionReady": False,
        "fetchedAt": result.get("fetchedAt"),
        "raw": data,
    }


def build_block(resolved: dict) -> tuple[dict, dict]:
    now = now_iso()
    status = {
        "status": "DATA_BLOCK",
        **resolved,
        "provider": "Twelve Data",
        "sourceType": "direct_api_strict_registry",
        "currentPrice": None,
        "quoteTimestampVerified": False,
        "strictV74PriceFresh": False,
        "executionSpreadVerified": False,
        "executionReady": False,
        "updatedAt": now,
    }
    latest = {"status": "DATA_BLOCK", "resolution": resolved, "updatedAt": now}
    return status, latest


def fetch_full(value: str, include_m1: bool = True) -> tuple[dict, dict]:
    resolved = resolve_symbol(value)
    if resolved.get("status") != "ok":
        return build_block(resolved)

    keys = ["D1", "H4", "H1", "M15", "M5"] + (["M1"] if include_m1 else [])
    frames = {key: fetch_frame(resolved, key) for key in keys}
    blocked_frames = [k for k, v in frames.items() if v.get("status") == "DATA_BLOCK"]
    failed_frames = [k for k, v in frames.items() if v.get("status") != "ok"]
    if blocked_frames:
        block = {
            "status": "DATA_BLOCK",
            **resolved,
            "reason": "PROVIDER_METADATA_MISMATCH",
            "message": f"Twelve Data metadata failed strict validation on: {blocked_frames}",
        }
        return build_block(block)

    quote = fetch_quote(resolved)
    if quote.get("status") != "ok":
        block = {
            "status": "DATA_BLOCK",
            **resolved,
            "reason": "CURRENT_QUOTE_UNAVAILABLE",
            "message": quote.get("error") or "Current quote could not be verified.",
        }
        return build_block(block)

    analysis_keys = ["D1", "H4", "H1", "M15", "M5"]
    analysis_ready = all(frames.get(k, {}).get("status") == "ok" for k in analysis_keys)
    now = now_iso()
    status = {
        "status": "ok" if analysis_ready else "partial",
        "requestedSymbol": resolved["requestedSymbol"],
        "returnedSymbol": resolved["requestedSymbol"],
        "marketSymbol": resolved["marketSymbol"],
        "marketType": resolved["marketType"],
        "instrumentName": resolved["instrumentName"],
        "expectedType": resolved["expectedType"],
        "provider": "Twelve Data",
        "sourceExchange": quote.get("exchange"),
        "sourceType": "direct_api_strict_metadata",
        "clientVersion": VERSION,
        "currentPrice": quote.get("currentPrice"),
        "currentPriceTime": quote.get("quoteTimestampISO"),
        "priceFetchedAt": quote.get("fetchedAt"),
        "priceType": quote.get("priceType"),
        "bid": None,
        "ask": None,
        "spread": None,
        "quoteAgeMs": quote.get("quoteAgeMs"),
        "quoteTimestampVerified": quote.get("quoteTimestampVerified"),
        "priceFreshnessType": "TWELVEDATA_LAST_QUOTE_AT",
        "strictV74PriceFresh": quote.get("strictV74PriceFresh"),
        "executionSpreadVerified": False,
        "executionReady": False,
        "marketClosedPossible": quote.get("isMarketOpen") is False,
        "symbolVerified": True,
        "analysisReady": analysis_ready,
        "successfulFrames": sum(1 for k in analysis_keys if frames.get(k, {}).get("status") == "ok"),
        "failedFrames": sum(1 for k in analysis_keys if frames.get(k, {}).get("status") != "ok"),
        "frames": {k: frames[k] for k in analysis_keys},
        "M1Reference": frames.get("M1"),
        "dataIntegrity": {
            "canonicalMappingVerified": True,
            "timeSeriesMetadataVerified": not bool(failed_frames),
            "exactQuoteTimestampVerified": quote.get("quoteTimestampVerified"),
            "spreadVerified": False,
            "marketEntryNeedsVenueConfirmation": True,
            "closedCandlesOnly": True,
        },
        "updatedAt": now,
    }
    latest = {
        "status": status["status"],
        "resolution": resolved,
        "quote": quote,
        "timeframes": frames,
        "updatedAt": now,
    }
    return status, latest


def write_outputs(value: str, out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    status, latest = fetch_full(value, include_m1=True)
    with open(os.path.join(out_dir, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({
        "status": status.get("status"),
        "requestedSymbol": status.get("requestedSymbol"),
        "marketSymbol": status.get("marketSymbol"),
        "marketType": status.get("marketType"),
        "provider": status.get("provider"),
        "currentPrice": status.get("currentPrice"),
        "currentPriceTime": status.get("currentPriceTime"),
        "quoteAgeMs": status.get("quoteAgeMs"),
        "strictV74PriceFresh": status.get("strictV74PriceFresh"),
        "executionReady": status.get("executionReady"),
        "reason": status.get("reason"),
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: twelvedata_market.py SYMBOL OUTPUT_DIR", file=sys.stderr)
        return 2
    return write_outputs(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    raise SystemExit(main())
