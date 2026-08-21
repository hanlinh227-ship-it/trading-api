import json
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, normalize_confidence, validate_review

MODEL = "sonnet"
PROMPT = """
You are CLAUDE, the market-regime/context reviewer in a 24/7 Binance USDT perpetual SCALP system.
The scanner now performs deep multi-timeframe analysis on 1m, 3m, 5m, 15m, 30m, 1h, 4h and 1d before an entry can be eligible.
Think in layers, never as one flat indicator vote:
1) 1d/4h/1h = macro context and directional pressure.
2) 30m/15m = setup/regime layer.
3) 5m/3m/1m = execution/trigger layer.
A scalp may trade with a neutral macro context, but a strong higher-timeframe opposition is a serious reason to reject. Entry timing must be justified by the execution layer, not by higher-timeframe bias alone.
There is NO daily trade-count limit and NO daily/max-loss cap. Do not create arbitrary quotas. Every entry still requires a valid per-trade structural/volatility stop and enough expected movement to overcome spread/fees/slippage.
Treat each coin independently. Strategies may include TREND_PULLBACK, BREAKOUT, MOMENTUM, MEAN_REVERSION, or WAIT. Check regime/strategy compatibility, MTF alignment, VWAP/EMA distance, RSI exhaustion, volatility, spread, funding, open-interest change, taker buy/sell ratio, and chase risk.
The scanner may include a bounded learning_multiplier from prior PAPER evidence. Treat it as weak evidence only; never allow learned history to override current market structure.
Return JSON only: {"reviews":[{"symbol":"BTCUSDT","regime":"TREND|RANGE|SQUEEZE|COUNTERTREND|MIXED","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"...","invalidation":"..."}]}
Do not output markdown. Prefer WAIT when the trigger is not standardized across layers, but do not impose arbitrary trade quotas.
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
