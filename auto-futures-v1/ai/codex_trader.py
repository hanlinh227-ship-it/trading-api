import json
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, normalize_confidence, validate_review

MODEL = "gpt-5.6-sol"
PROMPT = """
You are CODEX, the quantitative/logical verifier in a 24/7 Binance perpetual SCALP system.
No daily trade-count limit and no daily/max-loss cap are used. Do not add arbitrary quotas. Verify whether each proposed scalp is internally coherent.
Check direction against 1m/5m/15m data, strategy/regime compatibility, stop geometry, ATR/noise distance, target realism, volume, momentum, VWAP/EMA extension, and whether the trade is likely to be consumed by noise/fees/slippage.
Strategies are coin- and regime-specific: TREND_PULLBACK, BREAKOUT, MOMENTUM, MEAN_REVERSION. Reject mathematically inconsistent trades.
Return JSON only: {"reviews":[{"symbol":"BTCUSDT","regime":"TREND|RANGE|SQUEEZE|CHAOTIC","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"...","invalidation":"..."}]}
Do not output markdown or any explanation outside JSON.
"""


def main():
    snap = load_snapshot()
    setups = [compact_setup(x) for x in candidate_setups(snap)]
    payload = PROMPT + "\nMARKET_DATA:\n" + json.dumps(setups, ensure_ascii=False)
    try:
        p = subprocess.run(["/usr/bin/codex", "exec", payload], capture_output=True, text=True, timeout=180)
    except Exception as exc:
        print(json.dumps({"status":"ERROR","error":repr(exc),"reviews":{}})); return
    if p.returncode != 0:
        print(json.dumps({"status":"ERROR","error":p.stderr[-1500:],"reviews":{}})); return
    text = p.stdout.strip(); a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        print(json.dumps({"status":"INVALID_JSON","error":text[-1000:],"reviews":{}})); return
    try:
        obj = json.loads(text[a:b+1])
    except Exception as exc:
        print(json.dumps({"status":"INVALID_JSON","error":str(exc),"reviews":{}})); return
    clean = {}
    for r in obj.get("reviews", []):
        if not validate_review(r):
            continue
        sym = str(r["symbol"]).upper()
        clean[sym] = {"symbol":sym,"regime":str(r.get("regime","UNKNOWN")).upper(),"strategy":str(r.get("strategy","NO_EDGE")).upper(),"action":str(r.get("action","WAIT")).upper(),"confidence":normalize_confidence(r.get("confidence",0)),"reason":str(r.get("reason","")),"invalidation":str(r.get("invalidation",""))}
    print(json.dumps({"status":"OK","model":MODEL,"review_count":len(clean),"reviews":clean}, ensure_ascii=False))


if __name__ == "__main__":
    main()
