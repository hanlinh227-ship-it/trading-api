#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from market_registry import audit_symbols, classify, validate_identity

WORKER = "https://forex-chart-api.hanlinh227.workers.dev"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def http_json(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "trading-api-market-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"status": "error", "httpStatus": exc.code, "raw": body[:300]}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def crypto_audit(symbol):
    temp = tempfile.mkdtemp(prefix="crypto-audit-")
    try:
        proc = subprocess.run(
            ["python3", "scripts/fetch_crypto.py", symbol, temp],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if proc.returncode != 0:
            return {
                "symbol": symbol,
                "status": "FAIL",
                "marketType": "crypto",
                "errors": ["CRYPTO_FETCH_FAILED"],
                "stderr": proc.stderr[-500:],
            }
        with open(os.path.join(temp, "analysis.tmp.json"), encoding="utf-8") as f:
            analysis = json.load(f)
        with open(os.path.join(temp, "refresh.tmp.json"), encoding="utf-8") as f:
            refresh = json.load(f)
        m5 = (((analysis.get("timeframes") or {}).get("M5") or {}).get("summary") or {}).get("close")
        errors = validate_identity(symbol, refresh, m5)
        quote_age = refresh.get("quoteAgeMs")
        if refresh.get("bid") is None or refresh.get("ask") is None:
            errors.append("MISSING_EXCHANGE_BID_ASK")
        if quote_age is None or quote_age > 10_000:
            errors.append(f"CRYPTO_QUOTE_NOT_FRESH:{quote_age}")
        return {
            "symbol": symbol,
            "status": "PASS" if not errors else "FAIL",
            "marketType": "crypto",
            "provider": refresh.get("provider"),
            "marketSymbol": refresh.get("marketSymbol"),
            "currentPrice": refresh.get("currentPrice"),
            "currentPriceTime": refresh.get("currentPriceTime"),
            "quoteAgeMs": quote_age,
            "bid": refresh.get("bid"),
            "ask": refresh.get("ask"),
            "analysisFrames": f"{analysis.get('successfulFrames')}/5",
            "errors": errors,
        }
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def noncrypto_audit(symbol):
    spec = classify(symbol)
    analysis = http_json(f"{WORKER}/analysis/{symbol}")
    latest = http_json(f"{WORKER}/quote/{symbol}")
    endpoint = "quote"
    if latest.get("status") not in ("ok", "partial") or latest.get("currentPrice") is None:
        latest = http_json(f"{WORKER}/price/{symbol}")
        endpoint = "price"

    m5 = ((((analysis.get("timeframes") or {}).get("M5") or {}).get("summary") or {}).get("close"))
    errors = []
    if analysis.get("status") not in ("ok", "partial"):
        errors.append("ANALYSIS_PROVIDER_ERROR")
    if analysis.get("analysisReady") is not True or analysis.get("successfulFrames") != 5:
        errors.append("ANALYSIS_NOT_5_OF_5")
    if latest.get("status") not in ("ok", "partial"):
        errors.append("LATEST_PROVIDER_ERROR")
    errors += [f"ANALYSIS:{e}" for e in validate_identity(symbol, analysis, m5)]
    errors += [f"LATEST:{e}" for e in validate_identity(symbol, latest, m5)]

    # Exact futures must be provably futures. A commodity aggregate, cash index,
    # stock, or same-ticker security is a hard block.
    expected_block = spec["market_type"] == "futures" and any("MARKET_TYPE_MISMATCH" in e for e in errors)

    return {
        "symbol": symbol,
        "status": "BLOCKED_AS_DESIGNED" if expected_block else ("PASS" if not errors else "FAIL"),
        "marketTypeExpected": spec["market_type"],
        "providerSymbolExpected": spec["provider_symbol"],
        "provider": latest.get("provider") or analysis.get("provider"),
        "marketTypeReturned": latest.get("marketType") or analysis.get("marketType"),
        "marketSymbolReturned": latest.get("marketSymbol") or analysis.get("marketSymbol"),
        "currentPrice": latest.get("currentPrice"),
        "latestEndpoint": endpoint,
        "analysisFrames": f"{analysis.get('successfulFrames')}/5" if analysis else None,
        "errors": errors,
    }


def main():
    symbols = audit_symbols()
    crypto = [s for s in symbols if classify(s)["is_crypto"]]
    noncrypto = [s for s in symbols if not classify(s)["is_crypto"]]

    rows = []
    for symbol in crypto:
        rows.append(crypto_audit(symbol))

    # Grow55: analysis ~=5 credits + latest ~=1 credit per symbol. Keep each
    # round below the 55/min limit and allow the quota to reset between rounds.
    round_size = 8  # ~48 credits
    for start in range(0, len(noncrypto), round_size):
        batch = noncrypto[start:start + round_size]
        for symbol in batch:
            rows.append(noncrypto_audit(symbol))
        if start + round_size < len(noncrypto):
            time.sleep(62)

    failures = [r for r in rows if r["status"] == "FAIL"]
    blocked = [r for r in rows if r["status"] == "BLOCKED_AS_DESIGNED"]
    passed = [r for r in rows if r["status"] == "PASS"]

    output = {
        "generatedAt": now_iso(),
        "policy": "CANONICAL_INSTRUMENT_IDENTITY_AUDIT",
        "summary": {
            "total": len(rows),
            "pass": len(passed),
            "blockedAsDesigned": len(blocked),
            "fail": len(failures),
        },
        "rows": rows,
        "interpretation": {
            "PASS": "Provider returned the requested canonical instrument and passed sanity checks.",
            "BLOCKED_AS_DESIGNED": "Exact futures identity was not proven; refusing a proxy is correct behavior.",
            "FAIL": "Provider returned an ambiguous/wrong instrument or incomplete data and needs mapping/provider repair.",
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/market-data-audit.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(json.dumps(output, ensure_ascii=False, indent=2))
    # Audit itself succeeds even when rows FAIL so the evidence is committed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
