import json
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, normalize_confidence, validate_review

MODEL = "sonnet"
PROMPT = """
You are CLAUDE, the regime/context reviewer in a 24/7 Binance USDT perpetual SCALP system.
The system has NO daily trade-count limit and NO daily/max-loss cap. That does NOT mean reckless trading: every entry must have a real per-trade structural/volatility stop and plausible edge after fees/slippage.
Your specialty is market context, regime, and trade quality. Treat each coin independently; do not force one method across all coins.
Preferred strategies: TREND_PULLBACK, BREAKOUT, MOMENTUM, MEAN_REVERSION. Reject the scanner strategy when context disagrees.
Use 1m for trigger, 5m for setup, 15m for regime. Watch volume participation, VWAP/EMA distance, RSI exhaustion, volatility, funding/OI crowding, and chase risk.
Return JSON only: {"reviews":[{"symbol":"BTCUSDT","regime":"TREND|RANGE|SQUEEZE|CHAOTIC","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"...","invalidation":"..."}]}
Do not output markdown. Prefer WAIT when edge is unclear, but do not impose arbitrary trade quotas.
"""


def main():
    snap = load_snapshot()
    setups = [compact_setup(x) for x in candidate_setups(snap)]
    payload = PROMPT + "\nMARKET_DATA:\n" + json.dumps(setups, ensure_ascii=False)
    try:
        p = subprocess.run(["claude", "--model", MODEL, "-p", payload], capture_output=True, text=True, timeout=180)
    except Exception as exc:
        print(json.dumps({"status":"ERROR","error":repr(exc),"reviews":{}})); return
    if p.returncode != 0:
        print(json.dumps({"status":"ERROR","error":p.stderr[-1200:],"reviews":{}})); return
    text = p.stdout.strip(); a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        print(json.dumps({"status":"INVALID_JSON","reviews":{}})); return
    try:
        obj = json.loads(text[a:b+1])
    except Exception as exc:
        print(json.dumps({"status":"INVALID_JSON","error":str(exc),"reviews":{}})); return
    clean = {}
    for r in obj.get("reviews", []):
        if not validate_review(r):
            continue
        sym = str(r["symbol"]).upper()
        clean[sym] = {
            "symbol": sym,
            "regime": str(r.get("regime", "UNKNOWN")).upper(),
            "strategy": str(r.get("strategy", "NO_EDGE")).upper(),
            "action": str(r.get("action", "WAIT")).upper(),
            "confidence": normalize_confidence(r.get("confidence", 0)),
            "reason": str(r.get("reason", "")),
            "invalidation": str(r.get("invalidation", "")),
        }
    print(json.dumps({"status":"OK","model":MODEL,"review_count":len(clean),"reviews":clean}, ensure_ascii=False))


if __name__ == "__main__":
    main()
