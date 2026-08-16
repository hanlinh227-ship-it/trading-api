#!/usr/bin/env python3
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VERSION = "V1-GITHUB-DIRECT-CRYPTO"

BINANCE_BASE = "https://api.binance.com"
OKX_BASE = "https://www.okx.com"
BYBIT_BASE = "https://api.bybit.com"

CRYPTO_QUOTES = ["FDUSD", "USDT", "USDC", "USD", "BTC", "ETH", "BNB", "EUR"]

ANALYSIS_FRAMES = [
    {"key": "D1", "interval": "1day", "fetchSize": 220, "returnSize": 70},
    {"key": "H4", "interval": "4h", "fetchSize": 220, "returnSize": 90},
    {"key": "H1", "interval": "1h", "fetchSize": 220, "returnSize": 110},
    {"key": "M15", "interval": "15min", "fetchSize": 220, "returnSize": 120},
    {"key": "M5", "interval": "5min", "fetchSize": 220, "returnSize": 120},
]

REFRESH_FRAMES = [
    {"key": "M1", "interval": "1min", "fetchSize": 40, "returnSize": 20},
]


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_symbol(value):
    return str(value).upper().replace("/", "").replace("-", "").replace("_", "").replace(":", "").replace(" ", "").strip()


def parse_pair(symbol):
    s = clean_symbol(symbol)
    for quote in CRYPTO_QUOTES:
        if s.endswith(quote):
            base = s[:-len(quote)]
            if 2 <= len(base) <= 20 and base.isalnum() and base != quote:
                return base, quote
    return None


def http_json(url, timeout=15):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "trading-api-github-actions/1.0",
        },
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw[:500]}
        return {
            "ok": False,
            "httpStatus": e.code,
            "data": data,
            "latencyMs": int((time.time() - started) * 1000),
        }
    except Exception as e:
        return {
            "ok": False,
            "httpStatus": None,
            "error": str(e),
            "latencyMs": int((time.time() - started) * 1000),
        }

    try:
        data = json.loads(raw)
    except Exception:
        return {
            "ok": False,
            "httpStatus": status,
            "error": "INVALID_JSON",
            "raw": raw[:500],
            "latencyMs": int((time.time() - started) * 1000),
        }

    return {
        "ok": 200 <= status < 300,
        "httpStatus": status,
        "data": data,
        "latencyMs": int((time.time() - started) * 1000),
    }


def fnum(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = value * k + result * (1 - k)
    return result


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses += abs(diff)
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = abs(diff) if diff < 0 else 0.0
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
        cur = candles[i]
        prev = candles[i - 1]
        trs.append(max(
            cur["high"] - cur["low"],
            abs(cur["high"] - prev["close"]),
            abs(cur["low"] - prev["close"]),
        ))
    result = sum(trs[:period]) / period
    for tr in trs[period:]:
        result = (result * (period - 1) + tr) / period
    return result


def rnd(value, digits=8):
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def technical_summary(candles):
    if len(candles) < 20:
        return None
    closes = [c["close"] for c in candles]
    latest = candles[-1]
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    e200 = ema(closes, 200)
    r14 = rsi(closes, 14)
    a14 = atr(candles, 14)
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


def finalize_candles(candles, frame):
    candles = [c for c in candles if all(fnum(c.get(k)) is not None for k in ("open", "high", "low", "close"))]
    if not candles:
        return {
            "status": "error",
            "interval": frame["interval"],
            "candleCount": 0,
            "error": "NO_VALID_CANDLES",
        }
    candles.sort(key=lambda c: c["datetime"])
    latest = candles[-1]
    compact = [
        [c["datetime"], c["open"], c["high"], c["low"], c["close"], c.get("volume")]
        for c in candles[-frame["returnSize"]:]
    ]
    return {
        "status": "ok",
        "interval": frame["interval"],
        "candleCount": len(candles),
        "latestCandle": latest,
        "summary": technical_summary(candles),
        "candles": compact,
    }


def binance_ticker(symbol):
    url = f"{BINANCE_BASE}/api/v3/ticker/24hr?symbol={urllib.parse.quote(symbol)}"
    res = http_json(url)
    if not res.get("ok"):
        data = res.get("data") or {}
        return None, data.get("msg") or res.get("error") or f"HTTP_{res.get('httpStatus')}"
    data = res["data"]
    last = fnum(data.get("lastPrice"))
    if last is None:
        return None, "INVALID_PRICE"
    ts_ms = fnum(data.get("closeTime"))
    ts = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z") if ts_ms else now_iso()
    return {
        "status": "ok",
        "exchange": "Binance",
        "symbol": symbol,
        "lastPrice": last,
        "bid": fnum(data.get("bidPrice")),
        "ask": fnum(data.get("askPrice")),
        "timestamp": ts,
        "serverTimestamp": now_iso(),
        "latencyMs": res.get("latencyMs"),
        "volume24h": fnum(data.get("volume")),
        "quoteVolume24h": fnum(data.get("quoteVolume")),
    }, None


def binance_interval(interval):
    return {"1min": "1m", "5min": "5m", "15min": "15m", "1h": "1h", "4h": "4h", "1day": "1d"}.get(interval)


def binance_klines(symbol, frame):
    interval = binance_interval(frame["interval"])
    if not interval:
        return {"status": "error", "interval": frame["interval"], "candleCount": 0, "error": "INTERVAL_UNSUPPORTED"}
    limit = min(frame["fetchSize"], 1000)
    url = f"{BINANCE_BASE}/api/v3/klines?symbol={urllib.parse.quote(symbol)}&interval={interval}&limit={limit}"
    res = http_json(url)
    if not res.get("ok") or not isinstance(res.get("data"), list):
        data = res.get("data") or {}
        return {"status": "error", "interval": frame["interval"], "candleCount": 0, "error": data.get("msg") if isinstance(data, dict) else res.get("error") or f"HTTP_{res.get('httpStatus')}"}
    candles = []
    for row in res["data"]:
        candles.append({
            "datetime": datetime.fromtimestamp(float(row[0]) / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "open": fnum(row[1]),
            "high": fnum(row[2]),
            "low": fnum(row[3]),
            "close": fnum(row[4]),
            "volume": fnum(row[5]),
        })
    return finalize_candles(candles, frame)


def okx_ticker(base, quote):
    inst = f"{base}-{quote}"
    url = f"{OKX_BASE}/api/v5/market/ticker?instId={urllib.parse.quote(inst)}"
    res = http_json(url)
    data = res.get("data") or {}
    rows = data.get("data") if isinstance(data, dict) else None
    if not res.get("ok") or not isinstance(rows, list) or not rows:
        return None, (data.get("msg") if isinstance(data, dict) else None) or res.get("error") or f"HTTP_{res.get('httpStatus')}"
    item = rows[0]
    last = fnum(item.get("last"))
    if last is None:
        return None, "INVALID_PRICE"
    ts_ms = fnum(item.get("ts"))
    ts = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z") if ts_ms else now_iso()
    return {
        "status": "ok",
        "exchange": "OKX",
        "symbol": inst,
        "lastPrice": last,
        "bid": fnum(item.get("bidPx")),
        "ask": fnum(item.get("askPx")),
        "timestamp": ts,
        "serverTimestamp": now_iso(),
        "latencyMs": res.get("latencyMs"),
        "volume24h": fnum(item.get("vol24h")),
        "quoteVolume24h": fnum(item.get("volCcy24h")),
    }, None


def okx_interval(interval):
    return {"1min": "1m", "5min": "5m", "15min": "15m", "1h": "1H", "4h": "4H", "1day": "1Dutc"}.get(interval)


def okx_klines(base, quote, frame):
    inst = f"{base}-{quote}"
    bar = okx_interval(frame["interval"])
    if not bar:
        return {"status": "error", "interval": frame["interval"], "candleCount": 0, "error": "INTERVAL_UNSUPPORTED"}
    limit = min(frame["fetchSize"], 300)
    url = f"{OKX_BASE}/api/v5/market/candles?instId={urllib.parse.quote(inst)}&bar={urllib.parse.quote(bar)}&limit={limit}"
    res = http_json(url)
    data = res.get("data") or {}
    rows = data.get("data") if isinstance(data, dict) else None
    if not res.get("ok") or not isinstance(rows, list):
        return {"status": "error", "interval": frame["interval"], "candleCount": 0, "error": (data.get("msg") if isinstance(data, dict) else None) or res.get("error") or f"HTTP_{res.get('httpStatus')}"}
    candles = []
    for row in rows:
        candles.append({
            "datetime": datetime.fromtimestamp(float(row[0]) / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "open": fnum(row[1]),
            "high": fnum(row[2]),
            "low": fnum(row[3]),
            "close": fnum(row[4]),
            "volume": fnum(row[5]),
        })
    return finalize_candles(candles, frame)


def bybit_ticker(symbol):
    url = f"{BYBIT_BASE}/v5/market/tickers?category=spot&symbol={urllib.parse.quote(symbol)}"
    res = http_json(url)
    data = res.get("data") or {}
    rows = ((data.get("result") or {}).get("list")) if isinstance(data, dict) else None
    if not res.get("ok") or data.get("retCode") != 0 or not isinstance(rows, list) or not rows:
        return None, (data.get("retMsg") if isinstance(data, dict) else None) or res.get("error") or f"HTTP_{res.get('httpStatus')}"
    item = rows[0]
    last = fnum(item.get("lastPrice"))
    if last is None:
        return None, "INVALID_PRICE"
    ts_ms = fnum(data.get("time"))
    ts = datetime.fromtimestamp(ts_ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z") if ts_ms else now_iso()
    return {
        "status": "ok",
        "exchange": "Bybit",
        "symbol": symbol,
        "lastPrice": last,
        "bid": fnum(item.get("bid1Price")),
        "ask": fnum(item.get("ask1Price")),
        "timestamp": ts,
        "serverTimestamp": now_iso(),
        "latencyMs": res.get("latencyMs"),
        "volume24h": fnum(item.get("volume24h")),
        "quoteVolume24h": fnum(item.get("turnover24h")),
    }, None


def bybit_interval(interval):
    return {"1min": "1", "5min": "5", "15min": "15", "1h": "60", "4h": "240", "1day": "D"}.get(interval)


def bybit_klines(symbol, frame):
    interval = bybit_interval(frame["interval"])
    if not interval:
        return {"status": "error", "interval": frame["interval"], "candleCount": 0, "error": "INTERVAL_UNSUPPORTED"}
    limit = min(frame["fetchSize"], 1000)
    url = f"{BYBIT_BASE}/v5/market/kline?category=spot&symbol={urllib.parse.quote(symbol)}&interval={interval}&limit={limit}"
    res = http_json(url)
    data = res.get("data") or {}
    rows = ((data.get("result") or {}).get("list")) if isinstance(data, dict) else None
    if not res.get("ok") or data.get("retCode") != 0 or not isinstance(rows, list):
        return {"status": "error", "interval": frame["interval"], "candleCount": 0, "error": (data.get("retMsg") if isinstance(data, dict) else None) or res.get("error") or f"HTTP_{res.get('httpStatus')}"}
    candles = []
    for row in rows:
        candles.append({
            "datetime": datetime.fromtimestamp(float(row[0]) / 1000, timezone.utc).isoformat().replace("+00:00", "Z"),
            "open": fnum(row[1]),
            "high": fnum(row[2]),
            "low": fnum(row[3]),
            "close": fnum(row[4]),
            "volume": fnum(row[5]),
        })
    return finalize_candles(candles, frame)


def source_ticker(source, symbol, base, quote):
    if source == "Binance":
        return binance_ticker(symbol)
    if source == "OKX":
        return okx_ticker(base, quote)
    if source == "Bybit":
        return bybit_ticker(symbol)
    return None, "UNKNOWN_SOURCE"


def source_klines(source, symbol, base, quote, frame):
    if source == "Binance":
        return binance_klines(symbol, frame)
    if source == "OKX":
        return okx_klines(base, quote, frame)
    if source == "Bybit":
        return bybit_klines(symbol, frame)
    return {"status": "error", "interval": frame["interval"], "candleCount": 0, "error": "UNKNOWN_SOURCE"}


def select_source(symbol, base, quote):
    attempts = []
    for source in ["Binance", "OKX", "Bybit"]:
        ticker, error = source_ticker(source, symbol, base, quote)
        if not ticker:
            attempts.append({"source": source, "ok": False, "error": error})
            continue
        probe = source_klines(source, symbol, base, quote, REFRESH_FRAMES[0])
        if probe.get("status") != "ok":
            attempts.append({"source": source, "ok": False, "error": probe.get("error") or "KLINE_PROBE_FAILED"})
            continue
        attempts.append({"source": source, "ok": True, "error": None})
        return source, ticker, attempts
    return None, None, attempts


def age_ms(timestamp):
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() * 1000))
    except Exception:
        return None


def quote_stale(timestamp):
    age = age_ms(timestamp)
    return age is None or age > 30000


def spread(bid, ask):
    if bid is None or ask is None:
        return None
    return ask - bid


def build_response(symbol, base, quote, source, ticker, frames, results, mode):
    frame_status = {}
    successful = 0
    for frame in frames:
        result = results.get(frame["key"]) or {}
        if result.get("status") == "ok":
            successful += 1
        frame_status[frame["key"]] = {
            "status": result.get("status", "error"),
            "interval": frame["interval"],
            "candleCount": result.get("candleCount", 0),
            "latestTime": (result.get("latestCandle") or {}).get("datetime"),
            "error": result.get("error"),
            "code": result.get("code"),
        }
    failed = len(frames) - successful
    ready = successful == len(frames)
    if mode == "analysis":
        price_frame = results.get("M5") or {}
        price_type = "direct_exchange_last_price"
    else:
        price_frame = results.get("M1") or {}
        price_type = "direct_exchange_last_price"
    current_price_time = ticker.get("timestamp")
    quote_age = age_ms(current_price_time)
    return {
        "status": "ok" if ready else "partial",
        "workerVersion": VERSION,
        "provider": source,
        "sourceExchange": source,
        "sourceType": "github_runner_exchange_rest",
        "fallbackUsed": source != "Binance",
        "mode": mode,
        "symbol": symbol,
        "marketSymbol": f"{base}/{quote}",
        "marketType": "crypto",
        "generatedAt": now_iso(),
        "symbolVerified": True,
        "priceType": price_type,
        "currentPrice": ticker.get("lastPrice"),
        "currentPriceTime": current_price_time,
        "lastPrice": ticker.get("lastPrice"),
        "bid": ticker.get("bid"),
        "ask": ticker.get("ask"),
        "spread": spread(ticker.get("bid"), ticker.get("ask")),
        "priceTimestamp": current_price_time,
        "serverTimestamp": ticker.get("serverTimestamp"),
        "dataAgeSeconds": None if quote_age is None else quote_age // 1000,
        "quoteAgeMs": quote_age,
        "stale": quote_stale(current_price_time),
        "executionReady": ticker.get("lastPrice") is not None and not quote_stale(current_price_time),
        "marketClosedPossible": False,
        "analysisReady": ready,
        "successfulFrames": successful,
        "failedFrames": failed,
        "requestedTimeframes": [f["key"] for f in frames],
        "frameStatus": frame_status,
        "candleSchema": ["datetime", "open", "high", "low", "close", "volume"],
        "timeframes": results,
        "liveQuote": ticker,
        "candleReferencePrice": (price_frame.get("latestCandle") or {}).get("close"),
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_crypto.py SYMBOL OUTPUT_DIR", file=sys.stderr)
        return 2
    symbol = clean_symbol(sys.argv[1])
    out_dir = sys.argv[2].rstrip("/")
    pair = parse_pair(symbol)
    if not pair:
        print(f"Invalid crypto symbol: {symbol}", file=sys.stderr)
        return 2
    base, quote = pair
    source, ticker, attempts = select_source(symbol, base, quote)
    if not source:
        print(json.dumps({"status": "error", "error": "CRYPTO_SOURCE_UNAVAILABLE", "symbol": symbol, "attempts": attempts}, indent=2), file=sys.stderr)
        return 1

    analysis_results = {}
    for frame in ANALYSIS_FRAMES:
        analysis_results[frame["key"]] = source_klines(source, symbol, base, quote, frame)
    if sum(1 for v in analysis_results.values() if v.get("status") == "ok") != 5:
        print(json.dumps({"status": "error", "error": "ANALYSIS_FRAMES_FAILED", "source": source, "frameStatus": {k: v.get("error") for k, v in analysis_results.items()}}, indent=2), file=sys.stderr)
        return 1

    # Refresh ticker again immediately before final output.
    fresh_ticker, fresh_error = source_ticker(source, symbol, base, quote)
    if fresh_ticker:
        ticker = fresh_ticker

    refresh_results = {}
    for frame in REFRESH_FRAMES:
        refresh_results[frame["key"]] = source_klines(source, symbol, base, quote, frame)
    if refresh_results["M1"].get("status") != "ok":
        print(json.dumps({"status": "error", "error": "REFRESH_FRAME_FAILED", "source": source, "detail": refresh_results["M1"].get("error")}, indent=2), file=sys.stderr)
        return 1

    analysis = build_response(symbol, base, quote, source, ticker, ANALYSIS_FRAMES, analysis_results, "analysis")
    refresh = build_response(symbol, base, quote, source, ticker, REFRESH_FRAMES, refresh_results, "refresh")
    analysis["sourceAttempts"] = attempts
    refresh["sourceAttempts"] = attempts

    import os
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/analysis.tmp.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    with open(f"{out_dir}/refresh.tmp.json", "w", encoding="utf-8") as f:
        json.dump(refresh, f, ensure_ascii=False, indent=2)

    print("================================")
    print("CRYPTO SOURCE:", source)
    print("SYMBOL:", symbol)
    print("PRICE:", ticker.get("lastPrice"))
    print("BID:", ticker.get("bid"))
    print("ASK:", ticker.get("ask"))
    print("PRICE TIME:", ticker.get("timestamp"))
    print("EXECUTION READY:", refresh.get("executionReady"))
    print("FRAMES: 5/5 + M1")
    print("================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
