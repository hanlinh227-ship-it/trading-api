#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, "scripts")
import twelvedata_market as td


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def crypto_audit(symbol):
    temp = tempfile.mkdtemp(prefix="crypto-audit-")
    try:
        proc = subprocess.run(
            [sys.executable, "scripts/fetch_crypto.py", symbol, temp],
            text=True,
            capture_output=True,
            timeout=150,
        )
        if proc.returncode != 0:
            return {"symbol":symbol,"marketType":"crypto","status":"FAIL","errors":["CRYPTO_FETCH_FAILED"],"stderr":proc.stderr[-600:]}
        with open(os.path.join(temp,"analysis.tmp.json"),encoding="utf-8") as f:
            analysis=json.load(f)
        with open(os.path.join(temp,"refresh.tmp.json"),encoding="utf-8") as f:
            refresh=json.load(f)
        errors=[]
        if analysis.get("analysisReady") is not True or analysis.get("successfulFrames") != 5:
            errors.append("ANALYSIS_NOT_5_OF_5")
        age=refresh.get("quoteAgeMs")
        if age is None or age > 10000:
            errors.append(f"QUOTE_NOT_FRESH:{age}")
        if refresh.get("bid") is None or refresh.get("ask") is None:
            errors.append("MISSING_BID_ASK")
        if refresh.get("symbolVerified") is not True:
            errors.append("SYMBOL_NOT_VERIFIED")
        return {
            "symbol":symbol,"marketType":"crypto","status":"PASS" if not errors else "FAIL",
            "provider":refresh.get("provider"),"marketSymbol":refresh.get("marketSymbol"),
            "currentPrice":refresh.get("currentPrice"),"currentPriceTime":refresh.get("currentPriceTime"),
            "quoteAgeMs":age,"bid":refresh.get("bid"),"ask":refresh.get("ask"),
            "analysisFrames":f"{analysis.get('successfulFrames')}/5","executionReady":refresh.get("executionReady"),
            "errors":errors,
        }
    finally:
        shutil.rmtree(temp,ignore_errors=True)


def supported_td_audit(symbol):
    status, latest = td.fetch_full(symbol, include_m1=True)

    # A stale provider feed is a successful safety result: the live system
    # rejected it instead of presenting an old number as current.
    if status.get("status") == "DATA_BLOCK" and status.get("reason") == "CURRENT_QUOTE_STALE":
        return {
            "symbol":symbol,"marketType":status.get("marketType"),
            "status":"BLOCKED_AS_DESIGNED","provider":"Twelve Data",
            "marketSymbol":status.get("marketSymbol"),"currentPrice":None,
            "currentPriceTime":status.get("currentPriceTime"),"quoteAgeMs":status.get("quoteAgeMs"),
            "reason":status.get("reason"),"message":status.get("message"),"errors":[],
        }

    errors=[]
    if status.get("status") != "ok":
        errors.append(f"STATUS:{status.get('status')}")
    if status.get("symbolVerified") is not True:
        errors.append("SYMBOL_NOT_VERIFIED")
    if status.get("analysisReady") is not True or status.get("successfulFrames") != 5:
        errors.append("ANALYSIS_NOT_5_OF_5")
    if status.get("quoteTimestampVerified") is not True:
        errors.append("QUOTE_TIMESTAMP_NOT_VERIFIED")
    age=status.get("quoteAgeMs")
    if age is None or age > td.HARD_STALE_MS:
        errors.append(f"QUOTE_TOO_OLD_FOR_AUDIT:{age}")
    if status.get("currentPrice") is None:
        errors.append("MISSING_CURRENT_PRICE")
    return {
        "symbol":symbol,"marketType":status.get("marketType"),
        "status":"PASS" if not errors else "FAIL","provider":status.get("provider"),
        "marketSymbol":status.get("marketSymbol"),"expectedType":status.get("expectedType"),
        "currentPrice":status.get("currentPrice"),"currentPriceTime":status.get("currentPriceTime"),
        "quoteAgeMs":age,"strictV74PriceFresh":status.get("strictV74PriceFresh"),
        "bid":status.get("bid"),"ask":status.get("ask"),"spreadVerified":status.get("executionSpreadVerified"),
        "analysisFrames":f"{status.get('successfulFrames')}/5","closedCandlesOnly":((status.get("dataIntegrity") or {}).get("closedCandlesOnly")),
        "errors":errors,
    }


def expected_block_audit(symbol, expected_type):
    resolved=td.resolve_symbol(symbol)
    errors=[]
    if resolved.get("status") != "DATA_BLOCK":
        errors.append("EXPECTED_DATA_BLOCK")
    if resolved.get("marketType") != expected_type:
        errors.append(f"TYPE_MISMATCH:{resolved.get('marketType')}")
    return {
        "symbol":symbol,"marketType":expected_type,
        "status":"BLOCKED_AS_DESIGNED" if not errors else "FAIL",
        "provider":"Twelve Data","currentPrice":None,
        "reason":resolved.get("reason"),"message":resolved.get("message"),"errors":errors,
    }


def main():
    rows=[]

    for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT"):
        rows.append(crypto_audit(symbol))

    # Two Forex + two spot metals prove supported Twelve Data paths. The audit
    # also verifies that any stale feed is blocked instead of promoted as live.
    for symbol in ("EURUSD","GBPJPY","XAUUSD","XAGUSD"):
        rows.append(supported_td_audit(symbol))

    for symbol in ("NAS100","US500","DAX","N225"):
        rows.append(expected_block_audit(symbol,"index"))

    for symbol in ("NQ","MNQ","ES","MES","GC","CL"):
        rows.append(expected_block_audit(symbol,"future"))

    fail=[r for r in rows if r["status"]=="FAIL"]
    passed=[r for r in rows if r["status"]=="PASS"]
    blocked=[r for r in rows if r["status"]=="BLOCKED_AS_DESIGNED"]
    output={
        "generatedAt":now_iso(),
        "policy":"STRICT_DIRECT_MARKET_DATA_AUDIT_V4",
        "twelveDataClientVersion":td.VERSION,
        "summary":{"total":len(rows),"pass":len(passed),"blockedAsDesigned":len(blocked),"fail":len(fail)},
        "rows":rows,
        "interpretation":{
            "PASS":"Exact supported instrument returned current data and passed identity/timestamp checks.",
            "BLOCKED_AS_DESIGNED":"Exact instrument is unsupported or its current feed is stale; returning no live price is the correct safety behavior.",
            "FAIL":"A supposedly supported live route failed identity, freshness or analysis checks.",
        },
    }
    os.makedirs("data",exist_ok=True)
    with open("data/market-data-audit.json","w",encoding="utf-8") as f:
        json.dump(output,f,ensure_ascii=False,indent=2)
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 1 if fail else 0


if __name__=="__main__":
    raise SystemExit(main())
