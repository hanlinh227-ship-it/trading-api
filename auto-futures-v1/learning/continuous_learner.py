import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';LOGS=ROOT/'logs';POSITIONS=STATE/'paper_positions.json';POLICY=STATE/'adaptive_policy.json';REPORT=STATE/'learning_report.json'
MIN_TRADES_STRATEGY=30;MIN_TRADES_SYMBOL=40;MIN_TRADES_REGIME=30;MAX_MULTIPLIER_MOVE=0.15
BASE_CONFIDENCE=62;MIN_CONFIDENCE=58;MAX_CONFIDENCE=72

def now():return datetime.now(timezone.utc).isoformat()
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def clamp(x,lo,hi):return max(lo,min(hi,x))
def summarize(rows):
    n=len(rows);wins=[x for x in rows if x>0];losses=[x for x in rows if x<0];gp=sum(wins);gl=abs(sum(losses));net=sum(rows);avg=net/n if n else 0;wr=len(wins)/n if n else 0;pf=gp/gl if gl>0 else (9.99 if gp>0 else 0)
    return {'trades':n,'wins':len(wins),'losses':len(losses),'win_rate':round(wr,4),'net_pnl':round(net,8),'avg_pnl':round(avg,8),'profit_factor':round(pf,4)}
def learned_multiplier(stats,minimum):
    n=stats['trades']
    if n<minimum:return 1.0,'RESEARCH_ONLY'
    edge=clamp((stats['profit_factor']-1)/1.5,-1,1)*0.55+clamp((stats['win_rate']-.5)/.2,-1,1)*.30+(0.15 if stats['avg_pnl']>0 else -0.15 if stats['avg_pnl']<0 else 0)
    confidence=clamp((n-minimum)/max(minimum*3,1),0,1);move=clamp(edge*confidence*MAX_MULTIPLIER_MOVE,-MAX_MULTIPLIER_MOVE,MAX_MULTIPLIER_MOVE)
    return round(1+move,4),'ACTIVE_LEARNED'
def threshold_from_stats(stats,minimum):
    if stats['trades']<minimum:return BASE_CONFIDENCE,'RESEARCH_ONLY'
    pf=stats['profit_factor'];wr=stats['win_rate'];delta=0
    if pf<0.9 or wr<0.42:delta=8
    elif pf<1.05 or wr<0.47:delta=4
    elif pf>1.45 and wr>0.56:delta=-4
    elif pf>1.2 and wr>0.52:delta=-2
    return int(clamp(BASE_CONFIDENCE+delta,MIN_CONFIDENCE,MAX_CONFIDENCE)),'ACTIVE_LEARNED'
def main():
    state=load(POSITIONS,{'positions':[]});closed=[p for p in state.get('positions',[]) if p.get('status')=='CLOSED']
    by_strategy=defaultdict(list);by_symbol=defaultdict(list);by_regime=defaultdict(list);by_combo=defaultdict(list)
    for p in closed:
        x=float(p.get('realized_pnl',0) or 0);st=str(p.get('strategy','UNKNOWN'));sy=str(p.get('symbol','UNKNOWN'));rg=str(p.get('regime','UNKNOWN'));by_strategy[st].append(x);by_symbol[sy].append(x);by_regime[rg].append(x);by_combo[f'{sy}|{st}|{rg}'].append(x)
    ss={k:summarize(v) for k,v in by_strategy.items()};ys={k:summarize(v) for k,v in by_symbol.items()};rs={k:summarize(v) for k,v in by_regime.items()};cs={k:summarize(v) for k,v in by_combo.items()}
    sm={};sstatus={};sth={}
    for k,s in ss.items():sm[k],sstatus[k]=learned_multiplier(s,MIN_TRADES_STRATEGY);sth[k],_=threshold_from_stats(s,MIN_TRADES_STRATEGY)
    ym={};ystatus={};yth={}
    for k,s in ys.items():ym[k],ystatus[k]=learned_multiplier(s,MIN_TRADES_SYMBOL);yth[k],_=threshold_from_stats(s,MIN_TRADES_SYMBOL)
    rm={};rstatus={};rth={}
    for k,s in rs.items():rm[k],rstatus[k]=learned_multiplier(s,MIN_TRADES_REGIME);rth[k],_=threshold_from_stats(s,MIN_TRADES_REGIME)
    policy={'generated_at':now(),'status':'ACTIVE' if closed else 'DEFAULT_NO_CLOSED_TRADES','closed_trades':len(closed),'method':'bounded evidence-gated adaptive entry policy; no source-code self-modification','strategy_multipliers':sm,'symbol_multipliers':ym,'regime_multipliers':rm,'strategy_min_ai_confidence':sth,'symbol_min_ai_confidence':yth,'regime_min_ai_confidence':rth,'guardrails':{'minimum_strategy_trades':MIN_TRADES_STRATEGY,'minimum_symbol_trades':MIN_TRADES_SYMBOL,'minimum_regime_trades':MIN_TRADES_REGIME,'max_score_multiplier_move':MAX_MULTIPLIER_MOVE,'confidence_range':[MIN_CONFIDENCE,MAX_CONFIDENCE],'source_code_auto_rewrite':False,'paper_evidence_required':True,'never_learn_from_open_trade':True}}
    report={'generated_at':policy['generated_at'],'closed_trades':len(closed),'strategy_stats':ss,'symbol_stats':ys,'regime_stats':rs,'combo_stats':cs,'strategy_status':sstatus,'symbol_status':ystatus,'regime_status':rstatus,'policy':policy}
    STATE.mkdir(parents=True,exist_ok=True);LOGS.mkdir(parents=True,exist_ok=True);POLICY.write_text(json.dumps(policy,indent=2,ensure_ascii=False),encoding='utf-8');REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    with (LOGS/'learning.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'generated_at':policy['generated_at'],'closed_trades':len(closed),'strategy_multipliers':sm,'strategy_min_ai_confidence':sth})+'\n')
    print('='*72);print('CONTINUOUS ENTRY LEARNING POLICY');print('='*72);print('Closed trades:',len(closed),'| status:',policy['status'])
    for k,s in sorted(ss.items()):print('STRATEGY',k,'| N',s['trades'],'| WR',s['win_rate'],'| PF',s['profit_factor'],'| MULT',sm.get(k,1),'| MIN_CONF',sth.get(k,BASE_CONFIDENCE))
    print('Learning changes bounded weights/thresholds only. No source-code self-rewrite.')
if __name__=='__main__':main()
