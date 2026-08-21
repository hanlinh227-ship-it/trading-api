import json
import math
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('/opt/trading/trading-api/auto-futures-v1')
STATE=ROOT/'state'
SNAPSHOT_FILE=STATE/'market_snapshot.json'
CONSENSUS_FILE=STATE/'ai_consensus.json'
POSITIONS_FILE=STATE/'paper_positions.json'
POLICY_FILE=STATE/'adaptive_policy.json'
OUTPUT_FILE=STATE/'risk_decisions.json'

REQUIRE_AI_COUNT=3
BASE_MIN_AI_CONFIDENCE=62
MAX_LEVERAGE=3
MAX_CONCURRENT_POSITIONS=5
REQUIRED_DEEP_TIMEFRAMES={'1m','3m','5m','15m','30m','1h','4h','1d'}
BASE='https://fapi.binance.com'

def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default

def risk_pct_for_equity(equity):
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
        with urllib.request.urlopen(BASE+'/fapi/v1/exchangeInfo',timeout=15) as r:
            data=json.loads(r.read().decode())
        return {x.get('symbol'):x for x in data.get('symbols',[]) if x.get('symbol')}
    except Exception:
        return {}

def filter_by_type(info,kind):
    for f in info.get('filters',[]):
        if f.get('filterType')==kind:return f
    return {}

def floor_step(value,step):
    if step<=0:return value
    return math.floor((value+1e-15)/step)*step

def execution_feasibility(info,equity,entry,stop,risk_pct,leverage):
    try:
        entry=float(entry);stop=float(stop);equity=float(equity)
        distance=abs(entry-stop)
        if entry<=0 or distance<=0 or equity<=0:return False,'INVALID_EXECUTION_INPUT',0.0
        lot=filter_by_type(info,'MARKET_LOT_SIZE') or filter_by_type(info,'LOT_SIZE')
        step=float(lot.get('stepSize') or 0)
        min_qty=float(lot.get('minQty') or 0)
        notional_filter=filter_by_type(info,'MIN_NOTIONAL') or filter_by_type(info,'NOTIONAL')
        min_notional=float(notional_filter.get('notional') or notional_filter.get('minNotional') or 0)
        qty_risk=(equity*risk_pct/100.0)/distance
        qty_margin=(equity*leverage)/entry
        qty=floor_step(min(qty_risk,qty_margin),step)
        if qty<=0 or (min_qty>0 and qty<min_qty):
            return False,'QTY_BELOW_EXCHANGE_MIN',qty
        if min_notional>0 and qty*entry<min_notional:
            return False,'NOTIONAL_BELOW_EXCHANGE_MIN',qty
        return True,'PASS',qty
    except Exception:
        return False,'EXECUTION_FEASIBILITY_ERROR',0.0

def main():
    snapshot=load(SNAPSHOT_FILE,{'setups':[]})
    consensus=load(CONSENSUS_FILE,{'symbols':{}})
    state=load(POSITIONS_FILE,{'starting_equity':50.0,'equity':50.0,'positions':[]})
    policy=load(POLICY_FILE,{})
    ex=exchange_symbols()
    setups={x.get('symbol'):x for x in snapshot.get('setups',[]) if x.get('symbol')}
    positions=state.get('positions',[])
    open_positions=[p for p in positions if p.get('status')=='OPEN']
    open_symbols={p.get('symbol') for p in open_positions}
    open_count=len(open_positions)
    equity=float(state.get('equity',state.get('starting_equity',50.0)) or 50.0)
    risk_pct=risk_pct_for_equity(max(equity,.01))
    slots_left=max(0,MAX_CONCURRENT_POSITIONS-open_count)
    approvals_used=0
    decisions={}
    ranked=sorted(consensus.get('symbols',{}).items(),key=lambda kv:float((kv[1] or {}).get('average_confidence',0) or 0),reverse=True)

    for symbol,ai in ranked:
        action=str(ai.get('final_action','WAIT')).upper()
        setup=setups.get(symbol,{})
        strategy=str(setup.get('strategy','NO_EDGE')).upper()
        regime=str(setup.get('regime','UNKNOWN')).upper()
        min_conf=learned_min_conf(policy,symbol,strategy,regime)
        approved=False;reason='NO_TRADE';estimated_qty=0.0
        tf_keys=set((setup.get('timeframes') or {}).keys())
        mtf=setup.get('mtf_alignment') or {}
        info=ex.get(symbol,{})

        if action not in {'LONG','SHORT'}:reason='NO_EDGE'
        elif int(ai.get('available_reviewers',0))!=REQUIRE_AI_COUNT:reason='REQUIRE_3_AI'
        elif float(ai.get('average_confidence',0) or 0)<min_conf:reason='AI_CONFIDENCE_BELOW_LEARNED_THRESHOLD'
        elif symbol in open_symbols:reason='POSITION_ALREADY_OPEN'
        elif open_count+approvals_used>=MAX_CONCURRENT_POSITIONS:reason='MAX_5_CONCURRENT_POSITIONS'
        elif not REQUIRED_DEEP_TIMEFRAMES.issubset(tf_keys):reason='DEEP_MTF_INCOMPLETE'
        elif not mtf or setup.get('regime') in {None,'UNASSESSED_DEEP_MTF'}:reason='MTF_ALIGNMENT_MISSING'
        elif setup.get('candidate_action')!=action:reason='SCANNER_AI_CONFLICT'
        elif setup.get('blockers'):reason='SCANNER_BLOCKER'
        elif setup.get('entry') is None or setup.get('stop_loss') is None:reason='ENTRY_OR_STOP_MISSING'
        elif action=='LONG' and float(setup['stop_loss'])>=float(setup['entry']):reason='INVALID_LONG_STOP'
        elif action=='SHORT' and float(setup['stop_loss'])<=float(setup['entry']):reason='INVALID_SHORT_STOP'
        elif not info:reason='EXCHANGE_INFO_UNAVAILABLE'
        else:
            feasible,why,estimated_qty=execution_feasibility(info,equity,setup['entry'],setup['stop_loss'],risk_pct,MAX_LEVERAGE)
            if not feasible:reason=why
            else:
                approved=True;reason='PASS';approvals_used+=1

        decisions[symbol]={
            'action':action,'approved':approved,'reason':reason,'strategy':strategy,'regime':regime,
            'mtf_alignment':setup.get('mtf_alignment',{}),'learning_multiplier':setup.get('learning_multiplier',1.0),
            'learned_min_ai_confidence':min_conf,'spread_bps':setup.get('spread_bps'),'entry':setup.get('entry'),
            'stop_loss':setup.get('stop_loss'),'tp1':setup.get('tp1'),'tp2':setup.get('tp2'),'tp3':setup.get('tp3'),
            'management':setup.get('management',{}),'risk_pct':risk_pct,'max_leverage':MAX_LEVERAGE,
            'margin_mode':'ISOLATED','ai_confidence':ai.get('average_confidence',0),'estimated_order_qty':estimated_qty,
        }

    out={
        'generated_at':datetime.now(timezone.utc).isoformat(),'mode':'PAPER','engine':'V7_EXECUTION_AWARE_MAX5_RISK',
        'policy':{'style':'SCALP_ONLY_24_7','daily_trade_limit':None,'daily_loss_limit':None,'max_loss_limit':None,
                  'max_concurrent_positions':MAX_CONCURRENT_POSITIONS,'margin_mode':'ISOLATED_ONLY','refill_slot_after_position_done':True,
                  'stop_required_per_trade':True,'deep_mtf_required':sorted(REQUIRED_DEEP_TIMEFRAMES),
                  'adaptive_entry_thresholds':True,'execution_minimums_prechecked':True,'source_code_self_rewrite':False},
        'paper_equity':equity,'adaptive_risk_pct':risk_pct,'open_positions':open_count,'slots_left':slots_left,
        'suppress_new_trade_notifications':open_count>=MAX_CONCURRENT_POSITIONS,'decisions':decisions}
    OUTPUT_FILE.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print('='*56);print('V7 EXECUTION-AWARE RISK ENGINE');print('='*56)
    print('EQUITY:',equity,'| RISK/TRADE:',risk_pct,'% | OPEN',open_count,'/',MAX_CONCURRENT_POSITIONS,'| SLOTS',slots_left)
    for s,d in decisions.items():print(s,'|',d['action'],'| QTY',d['estimated_order_qty'],'|',d['reason'])
    print('UNTRADEABLE MIN-QTY/MIN-NOTIONAL SETUPS NEVER REACH HUB APPROVAL')
    print('NO REAL BINANCE ORDER AUTHORITY')

if __name__=='__main__':main()
