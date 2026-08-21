import json
import os
import urllib.request
import urllib.error
from common import load_snapshot, candidate_setups, compact_setup, normalize_confidence, validate_review

URL = "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
SYSTEM = """
You are DEEPSEEK, the adversarial reviewer in a 24/7 Binance perpetual SCALP system.
There is no daily trade-count limit and no daily/max-loss cap. Your job is NOT to add arbitrary quotas; your job is to find reasons a proposed scalp has no edge or has bad execution risk.
Attack each setup: stale momentum, low participation, fake breakout, crowded funding, weak structure, excessive EMA/VWAP extension, volatility too high/low, poor stop geometry, and reward that is unrealistic for the regime.
Use 1m trigger, 5m setup, 15m regime. Different coins may need different strategies: TREND_PULLBACK, BREAKOUT, MOMENTUM, MEAN_REVERSION.
Return JSON only: {"reviews":[{"symbol":"BTCUSDT","regime":"TREND|RANGE|SQUEEZE|CHAOTIC","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"...","invalidation":"..."}]}
Confidence means confidence in YOUR action, including WAIT. Do not output markdown.
"""


def main():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print(json.dumps({"status":"UNAVAILABLE","error":"DEEPSEEK_API_KEY_NOT_LOADED","reviews":{}})); return
    snap = load_snapshot()
    setups = [compact_setup(x) for x in candidate_setups(snap)]
    body = json.dumps({"model":MODEL,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(setups, ensure_ascii=False)}],"temperature":0.1,"max_tokens":3200,"stream":False}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status":"ERROR","error":f"HTTP_{exc.code}: {exc.read().decode(errors='replace')}","reviews":{}})); return
    except Exception as exc:
        print(json.dumps({"status":"ERROR","error":repr(exc),"reviews":{}})); return
    try:
        text = data["choices"][0]["message"]["content"].strip(); a, b = text.find("{"), text.rfind("}")
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
