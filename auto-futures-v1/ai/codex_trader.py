import json
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, normalize_confidence, validate_review

MODEL = "gpt-5.6-sol"
PROMPT = """
You are CODEX, the quantitative/logical verifier in a 24/7 Binance perpetual SCALP system.
Candidates are eligible only after deep analysis of 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d.
Verify the trade as a layered execution problem:
- Macro context: 1d/4h/1h.
- Setup/regime: 30m/15m.
- Trigger/execution: 5m/3m/1m.
Check that at least two execution timeframes support the direction, that setup layers do not materially oppose, and that higher-timeframe opposition is not strong enough to invalidate the scalp.
Check strategy/regime compatibility, stop geometry against ATR/noise, target distance versus estimated round-trip cost, spread, VWAP/EMA extension, volume participation, momentum, funding, open-interest change, and taker buy/sell ratio.
No daily trade-count limit and no daily/max-loss cap are used. Do not add arbitrary quotas. A trade is rejected only because execution/math/edge is weak.
The learning_multiplier is bounded historical PAPER evidence, not a command. Reject any historically favored setup that is incoherent now.
Strategies: TREND_PULLBACK, BREAKOUT, MOMENTUM, MEAN_REVERSION.
Return JSON only: {"reviews":[{"symbol":"BTCUSDT","regime":"TREND|RANGE|SQUEEZE|COUNTERTREND|MIXED","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"...","invalidation":"..."}]}
No markdown or text outside JSON.
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
