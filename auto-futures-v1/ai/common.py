import json
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
SNAPSHOT = STATE / "market_snapshot.json"
POLICY = STATE / "adaptive_policy.json"
MARKET_CONTEXT = STATE / "market_context.json"
COORDINATION = STATE / "ai_coordination_policy.json"

TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d")
VALID_ACTIONS = {"LONG", "SHORT", "WAIT"}
VALID_REGIMES = {"TREND", "RANGE", "SQUEEZE", "COUNTERTREND", "MIXED", "UNKNOWN"}

DECISION_CONTRACT = """
COMMON DECISION CONTRACT — obey exactly:
- Review only supplied candidates. Never invent symbols, prices or missing data.
- LONG/SHORT means THIS candidate is executable now in that direction; WAIT means do not enter now.
- Confidence is confidence in your returned ACTION, not generic directional strength.
- A role-specific concern may veto to WAIT. Do not reverse the scanner direction unless evidence clearly supports the opposite; normally use WAIT instead of flipping direction.
- Missing/unknown required evidence => WAIT, never assume favorable values.
- Historical/learning data is weak evidence and never overrides current market structure.
- Do not add daily trade quotas or portfolio rules. Judge only current edge/execution quality.
- Keep reasons factual and compact. Return every supplied symbol exactly once.
- JSON only, no markdown:
{"reviews":[{"symbol":"BTCUSDT","regime":"TREND|RANGE|SQUEEZE|COUNTERTREND|MIXED","strategy":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"<=18 words","invalidation":"<=12 words"}]}
""".strip()


def load_snapshot():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))

def load_optional(path):
    try:
        if path.exists(): return json.loads(path.read_text(encoding="utf-8"))
    except Exception: pass
    return {}

def candidate_setups(snapshot):
    items = snapshot.get("ai_candidates") or snapshot.get("setups") or []
    actionable = [x for x in items if str(x.get("candidate_action", "WAIT")).upper() in {"LONG", "SHORT"} and not (x.get("blockers") or [])]
    actionable.sort(key=lambda x:(float(x.get("setup_quality", x.get("setup_score", 0)) or 0),-float(x.get("spread_bps",999999) or 999999)),reverse=True)
    return actionable[:3]

def compact_setup(s):
    tfs=s.get("timeframes") or {};compact_tfs={}
    for tf in TIMEFRAMES:
        d=tfs.get(tf)
        if not isinstance(d,dict):continue
        compact_tfs[tf]={k:d.get(k) for k in ("trend","rsi","momentum","mom3","ema20_dist_pct","volume_ratio","atr_pct") if k in d}
    return {"symbol":str(s["symbol"]).upper(),"candidate_action":str(s.get("candidate_action","WAIT")).upper(),"strategy":str(s.get("strategy","NO_EDGE")).upper(),"regime":str(s.get("regime","UNKNOWN")).upper(),"setup_quality":s.get("setup_quality",s.get("setup_score",0)),"learning_multiplier":s.get("learning_multiplier",1.0),"entry":s.get("entry"),"stop_loss":s.get("stop_loss"),"tp1":s.get("tp1"),"tp2":s.get("tp2"),"tp3":s.get("tp3"),"funding_rate":s.get("funding_rate"),"open_interest_change_pct":s.get("open_interest_change_pct"),"taker_buy_sell_ratio":s.get("taker_buy_sell_ratio"),"spread_bps":s.get("spread_bps"),"estimated_roundtrip_cost_bps":s.get("estimated_roundtrip_cost_bps"),"timeframes":compact_tfs,"mtf_alignment":s.get("mtf_alignment",{}),"entry_standard":s.get("entry_standard",{}),"warnings":(s.get("warnings") or [])[:3],"management":s.get("management",{})}

def coordination_advisory():
    x=load_optional(COORDINATION);return {"generated_at":x.get("generated_at"),"repeated_conflicts":(x.get("repeated_conflicts") or [])[:3],"provider_health":x.get("provider_health",{})}

def normalize_confidence(value):
    try:value=float(value)
    except Exception:return 0.0
    if 0<=value<=1:value*=100
    return round(max(0.0,min(100.0,value)),2)

def normalize_review(r,supplied_symbols):
    if not isinstance(r,dict):return None
    sym=str(r.get("symbol","")).upper().strip()
    if not sym or sym not in supplied_symbols:return None
    action=str(r.get("action","WAIT")).upper().strip()
    if action not in VALID_ACTIONS:action="WAIT"
    regime=str(r.get("regime","UNKNOWN")).upper().strip()
    if regime not in VALID_REGIMES:regime="UNKNOWN"
    return {"symbol":sym,"regime":regime,"strategy":str(r.get("strategy","NO_EDGE")).upper()[:40],"action":action,"confidence":normalize_confidence(r.get("confidence",0)),"reason":str(r.get("reason",""))[:180],"invalidation":str(r.get("invalidation",""))[:140]}

def parse_review_response(text,setups):
    supplied={str(x.get("symbol","")).upper() for x in setups if x.get("symbol")}
    if not text or not supplied:return {},"EMPTY_OUTPUT" if supplied else "NO_CANDIDATES"
    a,b=text.find("{"),text.rfind("}")
    if a<0 or b<=a:return {},"INVALID_JSON"
    try:obj=json.loads(text[a:b+1])
    except Exception:return {},"INVALID_JSON"
    clean={}
    for raw in obj.get("reviews",[]):
        r=normalize_review(raw,supplied)
        if r:clean[r["symbol"]]=r
    missing=sorted(supplied-set(clean))
    for s in missing:
        clean[s]={"symbol":s,"regime":"UNKNOWN","strategy":"NO_EDGE","action":"WAIT","confidence":100.0,"reason":"REVIEW_MISSING_FROM_PROVIDER_OUTPUT","invalidation":"provider output incomplete"}
    return clean,("INCOMPLETE_OUTPUT" if missing else "OK")

def role_prompt(role_text):return role_text.strip()+"\n\n"+DECISION_CONTRACT
