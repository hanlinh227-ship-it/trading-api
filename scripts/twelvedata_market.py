#!/usr/bin/env python3
"""Strict, fast Twelve Data client for supported non-crypto markets.

V75 speed rules:
- explicit canonical symbol registry only;
- /time_series metadata must match exact symbol + instrument type;
- indicators use CLOSED candles only;
- D1/H4/H1/M15/M5 fetch in parallel;
- /quote proves identity and provides last_quote_at;
- /price is used only after quote identity is proven;
- M1 is optional and disabled by default;
- output candle tails are compact; indicators still use the full fetched history;
- quote older than 65 seconds is DATA_BLOCK;
- cash-index/futures aliases unsupported by current Grow55 are DATA_BLOCK;
- never invent broker bid/ask/spread.
"""
from __future__ import annotations

import concurrent.futures
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

VERSION = "V4-TWELVEDATA-FAST-STRICT"
BASE_URL = "https://api.twelvedata.com"
HARD_STALE_MS = 65_000
V74_FOREX_FRESH_MS = 30_000

FOREX_CCY = {
    "USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD","SGD","HKD",
    "NOK","SEK","DKK","PLN","CZK","HUF","MXN","ZAR","TRY","CNH","CNY",
}

COMMODITY_ALIASES = {
    "XAUUSD": ("XAU/USD","metal","Precious Metal","Gold Spot / US Dollar"),
    "GOLD": ("XAU/USD","metal","Precious Metal","Gold Spot / US Dollar"),
    "XAGUSD": ("XAG/USD","metal","Precious Metal","Silver Spot / US Dollar"),
    "SILVER": ("XAG/USD","metal","Precious Metal","Silver Spot / US Dollar"),
    "XPTUSD": ("XPT/USD","metal","Industrial Metal","Platinum Spot / US Dollar"),
    "XPDUSD": ("XPD/USD","metal","Industrial Metal","Palladium Spot / US Dollar"),
    "WTIUSD": ("WTI/USD","commodity_spot","Energy Resource","Crude Oil WTI Spot / US Dollar"),
    "WTI": ("WTI/USD","commodity_spot","Energy Resource","Crude Oil WTI Spot / US Dollar"),
    "BRENTUSD": ("XBR/USD","commodity_spot","Energy Resource","Brent Spot / US Dollar"),
    "BRENT": ("XBR/USD","commodity_spot","Energy Resource","Brent Spot / US Dollar"),
}

CASH_INDEX_ALIASES = {
    "NDX":"Nasdaq-100 cash index","NAS100":"Nasdaq-100 cash index",
    "NASDAQ100":"Nasdaq-100 cash index","USTEC":"Nasdaq-100 cash index",
    "SPX":"S&P 500 cash index","SP500":"S&P 500 cash index",
    "US500":"S&P 500 cash index","SPX500":"S&P 500 cash index",
    "DJI":"Dow Jones Industrial Average cash index","US30":"Dow Jones Industrial Average cash index",
    "DOW":"Dow Jones Industrial Average cash index","N225":"Nikkei 225 cash index",
    "JP225":"Nikkei 225 cash index","NIKKEI":"Nikkei 225 cash index",
    "NIKKEI225":"Nikkei 225 cash index","DAX":"DAX cash index","GDAXI":"DAX cash index",
    "DE40":"DAX cash index","GER40":"DAX cash index","FTSE":"FTSE 100 cash index",
    "UK100":"FTSE 100 cash index","CAC":"CAC 40 cash index","FR40":"CAC 40 cash index",
    "HSI":"Hang Seng cash index","VIX":"CBOE Volatility Index","RUT":"Russell 2000 cash index",
}

FUTURES_ALIASES = {
    "NQ":"E-mini Nasdaq-100 futures","MNQ":"Micro E-mini Nasdaq-100 futures",
    "ES":"E-mini S&P 500 futures","MES":"Micro E-mini S&P 500 futures",
    "GC":"COMEX Gold futures","SI":"COMEX Silver futures","CL":"NYMEX WTI Crude Oil futures",
}

# outputsize remains large enough for EMA200 / stable RSI+ATR.
# Returned candle tails are intentionally compact to make GitHub reads fast.
FRAME_SPECS = {
    "D1":("1day",220,12),
    "H4":("4h",220,16),
    "H1":("1h",220,20),
    "M15":("15min",220,28),
    "M5":("5min",220,36),
    "M1":("1min",80,16),
}
INTERVAL_SECONDS = {
    "1min":60,"5min":300,"15min":900,"30min":1800,"45min":2700,
    "1h":3600,"2h":7200,"4h":14400,"8h":28800,"1day":86400,
}


def now_utc():
    return datetime.now(timezone.utc)


def now_iso():
    return now_utc().isoformat().replace("+00:00","Z")


def clean_symbol(v):
    return (
        str(v).upper().replace("/","").replace("-","").replace("_","")
        .replace(":","").replace(" ","").strip()
    )


def fnum(v):
    try:
        n = float(v)
        return n if math.isfinite(n) else None
    except Exception:
        return None


def rnd(v, d=8):
    return None if v is None else round(float(v), d)


def td_key():
    key = os.environ.get("TWELVEDATA_API_KEY") or ""
    if not key:
        raise RuntimeError("TWELVEDATA_API_KEY is missing")
    return key


def request_json(endpoint, params=None, retries=2, timeout=35):
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    headers = {
        "Authorization": f"apikey {td_key()}",
        "Accept": "application/json",
        "User-Agent": "trading-api-twelvedata-fast-strict/4.0",
    }
    last = None
    for attempt in range(retries + 1):
        started = time.time()
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return {
                    "ok": True,
                    "httpStatus": r.status,
                    "data": json.loads(r.read().decode()),
                    "latencyMs": int((time.time() - started) * 1000),
                    "fetchedAt": now_iso(),
                }
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
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
            if e.code not in (429,500,502,503,504) or attempt >= retries:
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


def resolve_symbol(value):
    requested = clean_symbol(value)
    if requested in FUTURES_ALIASES:
        return {
            "status":"DATA_BLOCK",
            "requestedSymbol":requested,
            "marketType":"future",
            "instrumentName":FUTURES_ALIASES[requested],
            "reason":"TWELVE_DATA_FUTURES_NOT_AVAILABLE",
            "message":"Current Grow55 catalog/search does not expose the exact CME/COMEX/NYMEX contract. Never substitute a same-text ticker or spot proxy.",
        }
    if requested in CASH_INDEX_ALIASES:
        return {
            "status":"DATA_BLOCK",
            "requestedSymbol":requested,
            "marketType":"index",
            "instrumentName":CASH_INDEX_ALIASES[requested],
            "reason":"TWELVE_DATA_CASH_INDEX_NOT_USABLE_ON_GROW55",
            "message":"Exact cash index is not safely usable through current Grow55 core endpoints. Ambiguous NDX/SPX/DAX tickers are forbidden.",
        }
    if requested in COMMODITY_ALIASES:
        sym, mtype, etype, name = COMMODITY_ALIASES[requested]
        return {
            "status":"ok","requestedSymbol":requested,"marketSymbol":sym,
            "marketType":mtype,"expectedType":etype,"instrumentName":name,
        }
    if len(requested) == 6 and requested.isalpha():
        base, quote = requested[:3], requested[3:]
        if base in FOREX_CCY and quote in FOREX_CCY and base != quote:
            return {
                "status":"ok","requestedSymbol":requested,
                "marketSymbol":f"{base}/{quote}","marketType":"forex",
                "expectedType":"Physical Currency","instrumentName":f"{base}/{quote}",
            }
    return {
        "status":"DATA_BLOCK","requestedSymbol":requested,"marketType":"unknown",
        "reason":"SYMBOL_NOT_IN_STRICT_REGISTRY",
        "message":"Add an explicit canonical mapping before this symbol may be used.",
    }


def meta_matches(meta, resolved):
    if not isinstance(meta, dict):
        return False, "MISSING_META"
    if str(meta.get("symbol","")).upper() != resolved["marketSymbol"].upper():
        return False, f"META_SYMBOL_MISMATCH:{meta.get('symbol')}"
    if resolved.get("expectedType") and meta.get("type") != resolved["expectedType"]:
        return False, f"META_TYPE_MISMATCH:{meta.get('type')}"
    return True, None


def parse_dt(v):
    if not v:
        return None
    text = str(v).strip().replace("T"," ").replace("Z","")
    for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def is_closed_bar(v, interval):
    opened = parse_dt(v)
    seconds = INTERVAL_SECONDS.get(interval)
    return True if opened is None or seconds is None else opened + timedelta(seconds=seconds) <= now_utc()


def ema(values, p):
    if len(values) < p:
        return None
    r = sum(values[:p]) / p
    k = 2 / (p + 1)
    for v in values[p:]:
        r = v * k + r * (1 - k)
    return r


def rsi(values, p=14):
    if len(values) <= p:
        return None
    g = l = 0.0
    for i in range(1, p + 1):
        d = values[i] - values[i-1]
        g += max(d,0)
        l += max(-d,0)
    ag, al = g / p, l / p
    for i in range(p + 1, len(values)):
        d = values[i] - values[i-1]
        ag = (ag * (p-1) + max(d,0)) / p
        al = (al * (p-1) + max(-d,0)) / p
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - 100 / (1 + rs)


def atr(candles, p=14):
    if len(candles) <= p:
        return None
    trs = []
    for i in range(1, len(candles)):
        c, prev = candles[i], candles[i-1]
        trs.append(max(
            c["high"] - c["low"],
            abs(c["high"] - prev["close"]),
            abs(c["low"] - prev["close"]),
        ))
    r = sum(trs[:p]) / p
    for tr in trs[p:]:
        r = (r * (p-1) + tr) / p
    return r


def technical_summary(candles):
    if len(candles) < 20:
        return None
    closes = [c["close"] for c in candles]
    latest = candles[-1]
    e20, e50, e200 = ema(closes,20), ema(closes,50), ema(closes,200)
    r14, a14 = rsi(closes), atr(candles)
    recent = candles[-50:]
    trend = "neutral"
    if e20 is not None and e50 is not None:
        if latest["close"] > e20 > e50:
            trend = "bullish"
        elif latest["close"] < e20 < e50:
            trend = "bearish"
    return {
        "close":rnd(latest["close"]),
        "ema20":rnd(e20),"ema50":rnd(e50),"ema200":rnd(e200),
        "rsi14":rnd(r14,2),"atr14":rnd(a14),
        "recent50High":rnd(max(c["high"] for c in recent)),
        "recent50Low":rnd(min(c["low"] for c in recent)),
        "trend":trend,
    }


def fetch_frame(resolved, key):
    interval, fetch_size, return_size = FRAME_SPECS[key]
    res = request_json("time_series", {
        "symbol":resolved["marketSymbol"],
        "interval":interval,
        "outputsize":fetch_size,
        "timezone":"UTC",
        "order":"ASC",
    })
    if not res.get("ok"):
        data = res.get("data") or {}
        return {
            "status":"error","interval":interval,
            "error":data.get("message") or res.get("error") or f"HTTP_{res.get('httpStatus')}",
        }
    data = res.get("data") or {}
    ok, reason = meta_matches(data.get("meta") or {}, resolved)
    if not ok:
        return {
            "status":"DATA_BLOCK","interval":interval,"error":reason,
            "providerMeta":data.get("meta"),
        }
    candles = []
    for row in data.get("values") or []:
        o,h,l,c = (fnum(row.get(k)) for k in ("open","high","low","close"))
        if None in (o,h,l,c) or not is_closed_bar(row.get("datetime"), interval):
            continue
        candles.append({
            "datetime":row.get("datetime"),"open":o,"high":h,"low":l,"close":c,
            "volume":fnum(row.get("volume")),
        })
    candles.sort(key=lambda x:x["datetime"])
    if not candles:
        return {
            "status":"error","interval":interval,"error":"NO_CLOSED_CANDLES",
            "providerMeta":data.get("meta"),
        }
    latest = candles[-1]
    compact = [
        [c["datetime"],c["open"],c["high"],c["low"],c["close"],c.get("volume")]
        for c in candles[-return_size:]
    ]
    return {
        "status":"ok","interval":interval,"candleCount":len(candles),
        "latestCandle":latest,"summary":technical_summary(candles),
        "candles":compact,"providerMeta":data.get("meta"),
        "fetchedAt":res.get("fetchedAt"),
    }


def quote_age_ms(ts):
    try:
        return max(0, int((now_utc() - datetime.fromtimestamp(int(ts), timezone.utc)).total_seconds() * 1000))
    except Exception:
        return None


def fetch_quote(resolved):
    qres = request_json("quote", {"symbol":resolved["marketSymbol"],"timezone":"UTC"})
    if not qres.get("ok"):
        data = qres.get("data") or {}
        return {
            "status":"error",
            "error":data.get("message") or qres.get("error") or f"HTTP_{qres.get('httpStatus')}",
        }
    quote = qres.get("data") or {}
    if str(quote.get("symbol","")).upper() != resolved["marketSymbol"].upper():
        return {
            "status":"DATA_BLOCK",
            "error":f"QUOTE_SYMBOL_MISMATCH:{quote.get('symbol')}",
            "raw":quote,
        }
    quote_close = fnum(quote.get("close"))
    age = quote_age_ms(quote.get("last_quote_at"))
    if quote_close is None:
        return {"status":"error","error":"QUOTE_MISSING_CLOSE"}
    if age is None:
        return {"status":"DATA_BLOCK","error":"QUOTE_TIMESTAMP_MISSING"}

    pres = request_json("price", {"symbol":resolved["marketSymbol"]})
    if not pres.get("ok"):
        data = pres.get("data") or {}
        return {
            "status":"error",
            "error":data.get("message") or pres.get("error") or f"PRICE_HTTP_{pres.get('httpStatus')}",
        }
    latest = fnum((pres.get("data") or {}).get("price"))
    if latest is None:
        return {"status":"error","error":"PRICE_MISSING_VALUE"}
    drift = abs(latest - quote_close) / quote_close if quote_close else 0
    if drift > 0.05:
        return {
            "status":"DATA_BLOCK",
            "error":f"PRICE_VS_QUOTE_DRIFT_TOO_LARGE:{drift:.6f}",
            "quoteClose":quote_close,"latestPrice":latest,
        }

    stale = age > HARD_STALE_MS
    return {
        "status":"DATA_BLOCK" if stale else "ok",
        "error":f"QUOTE_STALE:{age}" if stale else None,
        "symbol":quote.get("symbol"),"name":quote.get("name"),
        "exchange":quote.get("exchange"),"micCode":quote.get("mic_code"),
        "currency":quote.get("currency"),
        "currentPrice":latest,"referenceQuoteClose":quote_close,
        "priceType":"twelvedata_price_validated_by_quote",
        "priceFetchedAt":pres.get("fetchedAt"),"quoteFetchedAt":qres.get("fetchedAt"),
        "quoteTimestamp":quote.get("last_quote_at"),
        "quoteTimestampISO":datetime.fromtimestamp(
            int(quote["last_quote_at"]), timezone.utc
        ).isoformat().replace("+00:00","Z"),
        "quoteAgeMs":age,"quoteTimestampVerified":True,
        "strictV74PriceFresh":age <= V74_FOREX_FRESH_MS,
        "hardStale":stale,"isMarketOpen":quote.get("is_market_open"),
        "bid":None,"ask":None,"spreadVerified":False,"executionReady":False,
    }


def build_block(resolved, extra=None):
    now = now_iso()
    merged = {**resolved, **(extra or {})}
    status = {
        "status":"DATA_BLOCK",**merged,"provider":"Twelve Data",
        "sourceType":"direct_api_strict_registry","currentPrice":None,
        "quoteTimestampVerified":False,"strictV74PriceFresh":False,
        "executionSpreadVerified":False,"executionReady":False,"updatedAt":now,
    }
    latest = {"status":"DATA_BLOCK","resolution":merged,"updatedAt":now}
    return status, latest


def fetch_full(value, include_m1=False):
    resolved = resolve_symbol(value)
    if resolved.get("status") != "ok":
        return build_block(resolved)

    keys = ["D1","H4","H1","M15","M5"] + (["M1"] if include_m1 else [])
    frames = {}
    quote = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(keys) + 1) as pool:
        frame_jobs = {pool.submit(fetch_frame, resolved, key): key for key in keys}
        quote_job = pool.submit(fetch_quote, resolved)
        for future in concurrent.futures.as_completed(frame_jobs):
            key = frame_jobs[future]
            try:
                frames[key] = future.result()
            except Exception as exc:
                frames[key] = {"status":"error","error":str(exc)}
        try:
            quote = quote_job.result()
        except Exception as exc:
            quote = {"status":"error","error":str(exc)}

    frames = {key:frames.get(key, {"status":"error","error":"MISSING_FRAME"}) for key in keys}
    blocked = [k for k,v in frames.items() if v.get("status") == "DATA_BLOCK"]
    failed = [k for k,v in frames.items() if v.get("status") != "ok"]
    if blocked:
        return build_block(resolved, {
            "reason":"PROVIDER_METADATA_MISMATCH",
            "message":f"Metadata failed strict validation on {blocked}",
        })

    if not quote or quote.get("status") != "ok":
        err = (quote or {}).get("error","")
        reason = "CURRENT_QUOTE_STALE" if err.startswith("QUOTE_STALE") else "CURRENT_QUOTE_UNAVAILABLE"
        return build_block(resolved, {
            "reason":reason,
            "message":err or "Current quote could not be verified.",
            "quoteAgeMs":(quote or {}).get("quoteAgeMs"),
            "currentPriceTime":(quote or {}).get("quoteTimestampISO"),
        })

    analysis_keys = ["D1","H4","H1","M15","M5"]
    ready = all(frames.get(k,{}).get("status") == "ok" for k in analysis_keys)
    now = now_iso()
    status = {
        "status":"ok" if ready else "partial",
        "requestedSymbol":resolved["requestedSymbol"],
        "returnedSymbol":resolved["requestedSymbol"],
        "marketSymbol":resolved["marketSymbol"],
        "marketType":resolved["marketType"],
        "instrumentName":resolved["instrumentName"],
        "expectedType":resolved["expectedType"],
        "provider":"Twelve Data",
        "sourceExchange":quote.get("exchange"),
        "sourceType":"direct_api_fast_strict_metadata",
        "clientVersion":VERSION,
        "currentPrice":quote.get("currentPrice"),
        "currentPriceTime":quote.get("quoteTimestampISO"),
        "priceFetchedAt":quote.get("priceFetchedAt"),
        "priceType":quote.get("priceType"),
        "bid":None,"ask":None,"spread":None,
        "quoteAgeMs":quote.get("quoteAgeMs"),
        "quoteTimestampVerified":True,
        "priceFreshnessType":"TWELVEDATA_LAST_QUOTE_AT_PLUS_PRICE",
        "strictV74PriceFresh":quote.get("strictV74PriceFresh"),
        "executionSpreadVerified":False,
        "executionReady":False,
        "marketClosedPossible":quote.get("isMarketOpen") is False,
        "symbolVerified":True,
        "analysisReady":ready,
        "successfulFrames":sum(1 for k in analysis_keys if frames.get(k,{}).get("status") == "ok"),
        "failedFrames":sum(1 for k in analysis_keys if frames.get(k,{}).get("status") != "ok"),
        "frames":{k:frames[k] for k in analysis_keys},
        "M1Reference":frames.get("M1"),
        "dataIntegrity":{
            "canonicalMappingVerified":True,
            "timeSeriesMetadataVerified":not bool(failed),
            "exactQuoteTimestampVerified":True,
            "latestPriceIdentityValidated":True,
            "spreadVerified":False,
            "marketEntryNeedsVenueConfirmation":True,
            "closedCandlesOnly":True,
            "hardStaleThresholdMs":HARD_STALE_MS,
            "parallelFrameFetch":True,
            "compactStoredCandles":True,
        },
        "updatedAt":now,
    }
    latest = {
        "status":status["status"],
        "resolution":resolved,
        "quote":{
            "status":quote.get("status"),
            "symbol":quote.get("symbol"),
            "name":quote.get("name"),
            "exchange":quote.get("exchange"),
            "currency":quote.get("currency"),
            "currentPrice":quote.get("currentPrice"),
            "referenceQuoteClose":quote.get("referenceQuoteClose"),
            "priceType":quote.get("priceType"),
            "priceFetchedAt":quote.get("priceFetchedAt"),
            "quoteTimestampISO":quote.get("quoteTimestampISO"),
            "quoteAgeMs":quote.get("quoteAgeMs"),
            "strictV74PriceFresh":quote.get("strictV74PriceFresh"),
            "isMarketOpen":quote.get("isMarketOpen"),
        },
        "timeframes":frames,
        "updatedAt":now,
    }
    return status, latest


def _frame_state(frame):
    summary = (frame or {}).get("summary") or {}
    trend = summary.get("trend")
    if trend == "bullish":
        return "BUY"
    if trend == "bearish":
        return "SELL"
    return "NEUTRAL"


def _m5_close_break(frame):
    candles = (frame or {}).get("candles") or []
    if len(candles) < 4:
        return "UNKNOWN"
    prev = candles[-4:-1]
    last = candles[-1]
    prev_high = max(float(c[2]) for c in prev)
    prev_low = min(float(c[3]) for c in prev)
    close = float(last[4])
    if close > prev_high:
        return "BULLISH_CLOSE_BREAK"
    if close < prev_low:
        return "BEARISH_CLOSE_BREAK"
    return "NO_CLOSE_BREAK"


def build_decision(status):
    if status.get("status") == "DATA_BLOCK":
        return {
            "status":"DATA_BLOCK",
            "symbol":status.get("requestedSymbol"),
            "marketType":status.get("marketType"),
            "reason":status.get("reason"),
            "message":status.get("message"),
            "currentPrice":None,
            "strictMarketReady":False,
            "updatedAt":status.get("updatedAt"),
        }

    frames = status.get("frames") or {}
    weights = {"D1":1,"H4":2,"H1":2,"M15":2,"M5":3}
    states = {tf:_frame_state(frames.get(tf)) for tf in weights}
    score = 0
    for tf, weight in weights.items():
        if states[tf] == "BUY":
            score += weight
        elif states[tf] == "SELL":
            score -= weight

    technical_bias = "BUY" if score >= 3 else "SELL" if score <= -3 else "NEUTRAL"
    m5_trigger = _m5_close_break(frames.get("M5"))
    price = status.get("currentPrice")
    m15s = (frames.get("M15") or {}).get("summary") or {}
    m5s = (frames.get("M5") or {}).get("summary") or {}
    atr15 = fnum(m15s.get("atr14"))

    def dist_r(level):
        lv = fnum(level)
        px = fnum(price)
        if lv is None or px is None or atr15 in (None,0):
            return None
        return rnd(abs(lv - px) / atr15, 3)

    summaries = {}
    latest_times = {}
    for tf in weights:
        frame = frames.get(tf) or {}
        summaries[tf] = frame.get("summary")
        latest_times[tf] = (frame.get("latestCandle") or {}).get("datetime")

    if not status.get("strictV74PriceFresh"):
        next_action = "REFRESH_PRICE"
    elif m5_trigger == "NO_CLOSE_BREAK":
        next_action = "WAIT_M5_CLOSE_TRIGGER"
    else:
        next_action = "CHECK_NEWS_AND_EXECUTION_VENUE"

    return {
        "status":"ok" if status.get("analysisReady") else "partial",
        "symbol":status.get("requestedSymbol"),
        "marketSymbol":status.get("marketSymbol"),
        "marketType":status.get("marketType"),
        "provider":status.get("provider"),
        "currentPrice":price,
        "currentPriceTime":status.get("currentPriceTime"),
        "quoteAgeMs":status.get("quoteAgeMs"),
        "strictV74PriceFresh":status.get("strictV74PriceFresh"),
        "spreadVerified":status.get("executionSpreadVerified"),
        "strictMarketReady":status.get("executionReady"),
        "technicalBias":technical_bias,
        "technicalScore":score,
        "frameDirection":states,
        "latestClosedCandleTime":latest_times,
        "summaries":summaries,
        "liquidity":{
            "H1High":((frames.get("H1") or {}).get("summary") or {}).get("recent50High"),
            "H1Low":((frames.get("H1") or {}).get("summary") or {}).get("recent50Low"),
            "M15High":m15s.get("recent50High"),
            "M15Low":m15s.get("recent50Low"),
            "M5High":m5s.get("recent50High"),
            "M5Low":m5s.get("recent50Low"),
            "distanceToM15HighR":dist_r(m15s.get("recent50High")),
            "distanceToM15LowR":dist_r(m15s.get("recent50Low")),
        },
        "m5TriggerPrefilter":m5_trigger,
        "recentM15Bars":((frames.get("M15") or {}).get("candles") or [])[-6:],
        "recentM5Bars":((frames.get("M5") or {}).get("candles") or [])[-8:],
        "nextAction":next_action,
        "rule":"Technical prefilter only. V74 still requires symbol-specific news/context, strict M5 MSS/displacement+retest and execution-venue spread before MARKET.",
        "updatedAt":status.get("updatedAt"),
    }


def write_outputs(value, out_dir, include_m1=False):
    os.makedirs(out_dir, exist_ok=True)
    status, latest = fetch_full(value, include_m1)
    decision = build_decision(status)
    with open(os.path.join(out_dir,"status.json"),"w",encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, separators=(",",":"))
    with open(os.path.join(out_dir,"latest.json"),"w",encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, separators=(",",":"))
    with open(os.path.join(out_dir,"decision.json"),"w",encoding="utf-8") as f:
        json.dump(decision, f, ensure_ascii=False, separators=(",",":"))
    print(json.dumps({
        k:status.get(k) for k in (
            "status","requestedSymbol","marketSymbol","marketType","provider",
            "currentPrice","currentPriceTime","quoteAgeMs","strictV74PriceFresh",
            "executionReady","reason"
        )
    }, ensure_ascii=False, indent=2))
    print(json.dumps({
        "technicalBias":decision.get("technicalBias"),
        "m5TriggerPrefilter":decision.get("m5TriggerPrefilter"),
        "nextAction":decision.get("nextAction"),
    }, ensure_ascii=False))
    return 0


def main():
    if len(sys.argv) < 3:
        print("Usage: twelvedata_market.py SYMBOL OUTPUT_DIR [--m1]", file=sys.stderr)
        return 2
    include_m1 = "--m1" in sys.argv[3:] or os.environ.get("INCLUDE_M1_REFERENCE") == "1"
    return write_outputs(sys.argv[1], sys.argv[2], include_m1)


if __name__ == "__main__":
    raise SystemExit(main())
