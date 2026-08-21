import json
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, normalize_confidence, validate_review

MODEL = "sonnet"
TIMEOUT_SECONDS = 55
PROMPT = """You are Claude, the context reviewer for Binance USDT perpetual scalps.
Review ONLY the supplied candidates. Use 1d/4h/1h for higher-timeframe pressure, 30m/15m for regime/setup, and 5m/3m/1m for trigger quality. Reject strong HTF opposition, exhausted/chased entries, poor spread/cost, or weak trigger alignment. Learning history is weak evidence only. No arbitrary daily trade quota.
Return compact JSON only:
{"reviews":[{"symbol":"...","regime":"TREND|RANGE|SQUEEZE|COUNTERTREND|MIXED","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"<=18 words","invalidation":"<=12 words"}]}
No markdown. Do not discuss symbols not supplied.
"""


def main():
    snap = load_snapshot()
    setups = [compact_setup(x) for x in candidate_setups(snap)]
    if not setups:
        print(json.dumps({"status":"OK","model":MODEL,"review_count":0,"reviews":{}})); return
    payload = PROMPT + "\nDATA=" + json.dumps(setups, ensure_ascii=False, separators=(",", ":"))
    try:
        p = subprocess.run(["claude", "--model", MODEL, "-p", payload], capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(json.dumps({"status":"TIMEOUT","timeout_seconds":TIMEOUT_SECONDS,"reviews":{}})); return
    except Exception as exc:
        print(json.dumps({"status":"ERROR","error":repr(exc),"reviews":{}})); return
    if p.returncode != 0:
        print(json.dumps({"status":"ERROR","error":p.stderr[-700:],"reviews":{}})); return
    text = p.stdout.strip(); a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        print(json.dumps({"status":"INVALID_JSON","reviews":{}})); return
    try:
        obj = json.loads(text[a:b+1])
    except Exception as exc:
        print(json.dumps({"status":"INVALID_JSON","error":str(exc),"reviews":{}})); return
    clean = {}
    supplied = {x["symbol"] for x in setups}
    for r in obj.get("reviews", []):
        if not validate_review(r):
            continue
        sym = str(r["symbol"]).upper()
        if sym not in supplied:
            continue
        clean[sym] = {
            "symbol": sym,
            "regime": str(r.get("regime", "UNKNOWN")).upper(),
            "strategy": str(r.get("strategy", "NO_EDGE")).upper(),
            "action": str(r.get("action", "WAIT")).upper(),
            "confidence": normalize_confidence(r.get("confidence", 0)),
            "reason": str(r.get("reason", ""))[:180],
            "invalidation": str(r.get("invalidation", ""))[:140],
        }
    print(json.dumps({"status":"OK","model":MODEL,"review_count":len(clean),"reviews":clean}, ensure_ascii=False))


if __name__ == "__main__":
    main()
