import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state'
SNAPSHOT_FILE=STATE/'market_snapshot.json';CONSENSUS_FILE=STATE/'ai_consensus.json';POSITIONS_FILE=STATE/'paper_positions.json';POLICY_FILE=STATE/'adaptive_policy.json';OUTPUT_FILE=STATE/'risk_decisions.json'
REQUIRE_AI_COUNT=3;BASE_MIN_AI_CONFIDENCE=62;MAX_LEVERAGE=3;MAX_CONCURRENT_POSITIONS=5
REQUIRED_DEEP_TIMEFRAMES={'1m','3m','5m','15m','30m','1h','4h','1d'};BASE='https://fapi.binance.com'

def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default

def research_risk_pct(equity):
    if equity<100:return 1.0
    if equity<250:return .75
    if equity<1000:return .60
    if equity<5000:return .50
    return .35

def learned_min_conf(policy,symbol,strategy,regime):
    vals=[BASE_MIN_AI_CONFIDENCE]
    for key,name in [('symbol_min_ai_confidence',symbol),('strategy_min_ai_confidence',strategy),('regime_min_ai_confidence',regime)]:
        try:
            if name in (policy.get(key) or {}):vals.append(float(policy[key][name]))
        except Exception:pass
    return max(58.0,min(72.0,max(vals)))

def exchange_symbols():
    try:
        with urllib.request.urlopen(BASE+'/fapi/v1/exchangeInfo',timeout=15) as r:data=json.loads(r.read().decode())
        return {x.get('symbol'):x for x in data.get('symbols',[]) if x.get('symbol')}
    except Exception:return {}

def main():
    snapshot=load(SNAPSHOT_FILE,{'setups':[]});consensus=load(CONSENSUS_FILE,{'symbols':{}});state=load(POSITIONS_FILE,{'starting_equity':50.0,'equity':50.0,'positions':[]});policy=load(POLICY_FILE,{})
    ex=exchange_symbols();setups={x.get('symbol'):x for x in snapshot.get('setups',[]) if x.get('symbol')};paper_open=[p for p in state.get('positions',[]) if p.get('status')=='OPEN']
    paper_equity=float(state.get('equity',state.get('starting_equity',50.0)) or 50.0);research_pct=research_risk_pct(max(paper_equity,.01));decisions={}
    ranked=sorted(consensus.get('symbols',{}).items(),key=lambda kv:float((kv[1] or {}).get('consensus_confidence',(kv[1] or {}).get('average_confidence',0)) or 0),reverse=True)
    for symbol,ai in ranked:
        action=str(ai.get('final_action','WAIT')).upper();setup=setups.get(symbol,{})
        strategy=str(setup.get('strategy','NO_EDGE')).upper();regime=str(setup.get('regime','UNKNOWN')).upper();min_conf=learned_min_conf(policy,symbol,strategy,regime)
        approved=False;reason='NO_TRADE';tf_keys=set((setup.get('timeframes') or {}).keys());mtf=setup.get('mtf_alignment') or {};info=ex.get(symbol,{})
        entry=setup.get('entry');stop=setup.get('stop_loss');tp1=setup.get('tp1');tp2=setup.get('tp2');tp3=setup.get('tp3');conf=float(ai.get('consensus_confidence',ai.get('average_confidence',0)) or 0)
        if action not in {'LONG','SHORT'}:reason='NO_EDGE'
        elif int(ai.get('available_reviewers',0))!=REQUIRE_AI_COUNT:reason='REQUIRE_3_AI'
        elif conf<min_conf:reason='AI_CONFIDENCE_BELOW_LEARNED_THRESHOLD'
        elif not REQUIRED_DEEP_TIMEFRAMES.issubset(tf_keys):reason='DEEP_MTF_INCOMPLETE'
        elif not mtf or setup.get('regime') in {None,'UNASSESSED_DEEP_MTF'}:reason='MTF_ALIGNMENT_MISSING'
        elif str(setup.get('candidate_action','')).upper()!=action:reason='SCANNER_AI_CONFLICT'
        elif setup.get('blockers'):reason='SCANNER_OR_SIGNAL_QUALITY_BLOCKER'
        elif entry is None:reason='ENTRY_MISSING'
        elif stop is None:reason='STOP_MISSING'
        elif tp1 is None or tp2 is None or tp3 is None:reason='TP_MISSING'
        elif action=='LONG' and not (float(stop)<float(entry)<float(tp3)):reason='INVALID_LONG_GEOMETRY'
        elif action=='SHORT' and not (float(stop)>float(entry)>float(tp3)):reason='INVALID_SHORT_GEOMETRY'
        elif not info or info.get('status')!='TRADING':reason='EXCHANGE_SYMBOL_NOT_TRADING'
        else:approved=True;reason='PASS'
        decisions[symbol]={
            'action':action,'approved':approved,'reason':reason,'strategy':strategy,'regime':regime,'mtf_alignment':mtf,
            'learning_multiplier':setup.get('learning_multiplier',1.0),'learned_min_ai_confidence':min_conf,'spread_bps':setup.get('spread_bps'),
            'entry':entry,'stop_loss':stop,'tp1':tp1,'tp2':tp2,'tp3':tp3,'management':setup.get('management',{}),
            'risk_pct_research_reference':research_pct,'max_leverage':MAX_LEVERAGE,'margin_mode':'ISOLATED','ai_confidence':conf,
            'signal_intelligence_score':setup.get('signal_intelligence_score'),'signal_intelligence':setup.get('signal_intelligence',{}),
            'live_order_qty_source':'BINANCE_LIVE_PREFLIGHT_ONLY','estimated_order_qty':None,
        }
    out={'generated_at':datetime.now(timezone.utc).isoformat(),'mode':'SIGNAL_RISK_ONLY_LIVE_SIZING_SEPARATE','engine':'V10_RISK_SIGNAL_APPROVAL',
         'policy':{'style':'SCALP_ONLY_24_7','daily_trade_limit':None,'daily_loss_limit':None,'max_loss_limit':None,'live_max_concurrent_positions':MAX_CONCURRENT_POSITIONS,
                   'live_capacity_enforced_by':'BINANCE_LIVE_PREFLIGHT_AND_EXECUTOR','live_quantity_enforced_by':'BINANCE_AVAILABLE_BALANCE_IN_PREFLIGHT','margin_mode':'ISOLATED_ONLY',
                   'deep_mtf_required':sorted(REQUIRED_DEEP_TIMEFRAMES),'three_ai_required':True,'signal_quality_guard_required':True,'source_code_self_rewrite':False},
         'paper_equity_research_only':paper_equity,'paper_risk_pct_research_only':research_pct,'paper_open_positions_research_only':len(paper_open),'decisions':decisions}
    OUTPUT_FILE.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print('='*64);print('V10 SIGNAL RISK ENGINE — LIVE SIZING SEPARATED');print('='*64)
    for s,d in decisions.items():print(s,'|',d['action'],'| CONF',d['ai_confidence'],'|',d['reason'])
    print('LIVE QTY SOURCE: BINANCE LIVE PREFLIGHT ONLY')
if __name__=='__main__':main()
