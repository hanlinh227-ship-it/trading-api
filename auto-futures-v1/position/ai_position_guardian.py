import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';POSITIONS=STATE/'paper_positions.json';CONSENSUS=STATE/'ai_consensus.json';SNAPSHOT=STATE/'market_snapshot.json';CONTEXT=STATE/'market_context.json';OUT=STATE/'position_management.json';BASE='https://fapi.binance.com'

def now():return datetime.now(timezone.utc).isoformat()
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def price(symbol):
    with urllib.request.urlopen(f'{BASE}/fapi/v1/ticker/price?symbol={symbol}',timeout=10) as r:return float(json.loads(r.read().decode())['price'])
def avg(xs):return sum(xs)/len(xs) if xs else 0.0

def main():
    state=load(POSITIONS,{'positions':[]});consensus=load(CONSENSUS,{'symbols':{}});snapshot=load(SNAPSHOT,{'setups':[]});market_context=load(CONTEXT,{'symbols':{}});setups={x.get('symbol'):x for x in snapshot.get('setups',[]) if x.get('symbol')};decisions={}
    for p in state.get('positions',[]):
        if p.get('status')!='OPEN':continue
        symbol=p.get('symbol');side=str(p.get('side','')).upper();opposite_side='SHORT' if side=='LONG' else 'LONG';entry=float(p.get('entry',0) or 0);current_stop=float(p.get('stop_loss',0) or 0);initial_risk=abs(float(p.get('initial_risk',0) or 0))
        if not symbol or entry<=0 or initial_risk<=0:continue
        try:px=price(symbol)
        except Exception:continue
        ai=consensus.get('symbols',{}).get(symbol,{});reviews=ai.get('reviews',{}) or {};valid=[r for r in reviews.values() if isinstance(r,dict)];actions=[str(r.get('action','WAIT')).upper() for r in valid];same_reviews=[r for r in valid if str(r.get('action','')).upper()==side];opp_reviews=[r for r in valid if str(r.get('action','')).upper()==opposite_side];same=len(same_reviews);opposite=len(opp_reviews);waits=actions.count('WAIT');same_conf=avg([float(r.get('confidence',0) or 0) for r in same_reviews]);opposition_conf=avg([float(r.get('confidence',0) or 0) for r in opp_reviews])
        setup=setups.get(symbol,{});candidate=str(setup.get('candidate_action','WAIT')).upper();blockers=list(setup.get('blockers') or []);warnings=list(setup.get('warnings') or []);ctx=(market_context.get('symbols') or {}).get(symbol,{});ret15=float(ctx.get('return_15m_pct',0) or 0);ret60=float(ctx.get('return_60m_pct',0) or 0);vol_impulse=float(ctx.get('volume_impulse_5m',0) or 0);funding=float(ctx.get('funding_rate',0) or 0)
        move_r=((px-entry)/initial_risk) if side=='LONG' else ((entry-px)/initial_risk);momentum_with=(ret15>0 and side=='LONG') or (ret15<0 and side=='SHORT');momentum_against=(ret15<0 and side=='LONG') or (ret15>0 and side=='SHORT');higher_momentum_against=(ret60<0 and side=='LONG') or (ret60>0 and side=='SHORT')
        action='HOLD';reason='STRUCTURE_INTACT';trail_factor=.90;reduce_fraction=0.0
        hard_invalidation=candidate==opposite_side or bool(blockers);strong_ai_reversal=opposite>=2 and opposition_conf>=64;three_ai_reversal=opposite==3 and opposition_conf>=58;losing_and_reversing=move_r<=-.35 and opposite>=2;context_reversal=momentum_against and higher_momentum_against and vol_impulse>=1.20
        if three_ai_reversal and (hard_invalidation or move_r<=.15):action='EXIT';reason='3AI_REVERSAL_PLUS_INVALIDATION'
        elif strong_ai_reversal and (losing_and_reversing or context_reversal or hard_invalidation):action='EXIT';reason='2AI_REVERSAL_CONFIRMED_BY_PRICE_CONTEXT'
        elif opposite>=2 and opposition_conf>=58:action='REDUCE';reduce_fraction=.50;trail_factor=.50;reason='AI_REVERSAL_RISK_REDUCE_HALF'
        elif opposite>=1 or same<2 or same_conf<55:action='HOLD_TIGHT';trail_factor=.65;reason='EDGE_WEAKENING_TIGHTEN'
        elif same==3 and same_conf>=72 and not blockers and (momentum_with or move_r>=.35):action='HOLD';trail_factor=1.00;reason='3AI_STRONG_HOLD_LET_WINNER_BREATHE'
        crowded_long=side=='LONG' and funding>.0005;crowded_short=side=='SHORT' and funding<-.0005
        if action=='HOLD' and (crowded_long or crowded_short) and momentum_against:action='HOLD_TIGHT';trail_factor=min(trail_factor,.70);reason='CROWDED_FUNDING_PLUS_ADVERSE_MOMENTUM'
        proposed=current_stop
        if move_r>=.65:
            be_buffer=.04*initial_risk;be=entry+be_buffer if side=='LONG' else entry-be_buffer;proposed=max(proposed,be) if side=='LONG' else min(proposed,be)
        if move_r>=.90 or action in {'HOLD_TIGHT','REDUCE'}:
            distance=initial_risk*trail_factor;trailing=px-distance if side=='LONG' else px+distance;proposed=max(proposed,trailing) if side=='LONG' else min(proposed,trailing)
        if side=='LONG':
            proposed=max(current_stop,proposed)
            if px>entry:proposed=min(proposed,px-initial_risk*.04)
        else:
            proposed=min(current_stop,proposed)
            if px<entry:proposed=max(proposed,px+initial_risk*.04)
        decisions[symbol]={'symbol':symbol,'side':side,'price':px,'entry':entry,'current_stop':current_stop,'proposed_stop':proposed,'move_r':round(move_r,4),'management_action':action,'reduce_fraction':reduce_fraction,'reason':reason,'ai_actions':actions,'same_direction_confidence':round(same_conf,2),'opposition_confidence':round(opposition_conf,2),'confidence_definition':'ACTION_SPECIFIC_NOT_GLOBAL_AVERAGE','same_direction_ai':same,'opposition_ai':opposite,'wait_ai':waits,'scanner_candidate_action':candidate,'scanner_blockers':blockers,'scanner_warnings':warnings,'market_context':{'return_15m_pct':ret15,'return_60m_pct':ret60,'volume_impulse_5m':vol_impulse,'funding_rate':funding},'trail_factor_r':trail_factor,'may_widen_stop':False,'may_increase_risk':False,'exit_requires_multi_evidence':True}
    payload={'generated_at':now(),'engine':'V9_ACTION_SPECIFIC_3AI_POSITION_GUARDIAN','policy':{'actions':['HOLD','HOLD_TIGHT','REDUCE','EXIT'],'review_open_positions_continuously':True,'never_widen_stop':True,'never_increase_post_entry_risk':True,'exit_requires_multi_evidence':True,'single_ai_opposition_never_forces_exit':True,'funding_alone_never_forces_exit':True,'confidence_is_action_specific':True,'breakeven_from_r':.65,'trailing_from_r':.90},'decisions':decisions};OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')
    print('='*64);print('3-AI + MARKET CONTEXT POSITION GUARDIAN V9');print('='*64);print('OPEN REVIEWED:',len(decisions))
    for s,d in decisions.items():print(s,'|',d['management_action'],'|',d['reason'],'| R',d['move_r'],'| SAME_CONF',d['same_direction_confidence'],'| OPP_CONF',d['opposition_confidence'])
    print('HARD RULE: NEVER WIDEN STOP / EXIT REQUIRES MULTI-EVIDENCE')
if __name__=='__main__':main()
