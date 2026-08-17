#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core

# LOCKED before either cutoff is evaluated. Both are untouched blind samples.
CUTOFFS=[
 ('BLIND_A_2026-07-28_12UTC','2026-07-28T12:00:00Z'),
 ('BLIND_B_2026-07-26_12UTC','2026-07-26T12:00:00Z'),
]
HOURS=96; LOOKBACK=48; STOP_FACTOR=.75

def same_sign(*xs):
    z=[1 if x>0 else -1 if x<0 else 0 for x in xs]
    z=[x for x in z if x]
    return len(set(z))<=1 if z else False

def decide(sym,f,su,model,breadth):
    fake={'available':False,'oiChange4h':None,'funding':None,'fundingZ':0.0,'signal':0.0}
    score=core.score_trade(sym,f,su,fake,breadth)
    side='BUY' if score>=0 else 'SELL'
    pos=model.get('rangePositionH1',.5);ch=model.get('chaseAdjustment',0);sw15=model.get('m15Sweep',0);sw5=model.get('m5Sweep',0)
    rsi=su['M15'].get('rsi14') or 50;dist=su['M15'].get('dist20ATR') or 0;ltf=model.get('ltfScore',0);htf=model.get('htfScore',0)
    override=None;reason=None
    # Forced-market exhaustion override: extreme range location plus stretch/rejection means continuation entries are late.
    top_exhaust=(pos>=.84 and (ch<=-1.2 or sw15==-1 or sw5==-1 or rsi>=68 or dist>=1.45))
    bot_exhaust=(pos<=.16 and (ch>=1.2 or sw15==1 or sw5==1 or rsi<=32 or dist<=-1.45))
    if side=='BUY' and top_exhaust:
        override='SELL';reason='upper_exhaustion'
    elif side=='SELL' and bot_exhaust:
        override='BUY';reason='lower_exhaustion'
    # Transition conflict: if HTF and execution disagree strongly, execution wins unless already at an exhaustion edge.
    elif model['regime']=='transition' and abs(ltf)>=3.2 and ((ltf>0)!=(score>0)) and .20<pos<.80:
        override='BUY' if ltf>0 else 'SELL';reason='transition_ltf_confirmation'
    final=override or side
    # Confidence is based on actual chosen direction, not absolute indicator count.
    sign=1 if final=='BUY' else -1
    alignment=sum(1 for x in (f['r6'],f['r24'],f['r72'],f['r7d']) if x*sign>0)
    structure_align=sum(1 for x in (f['st4'],f['st1']) if x*sign>0)
    strength=alignment + .75*structure_align + .25*(abs(score)>=2.5) + .25*(abs(htf)>=5)
    if reason in ('upper_exhaustion','lower_exhaustion'):
        rr=1.55 if (sw15 or sw5) else 1.50
    elif strength>=4.75 and model['regime']=='trend': rr=1.90
    elif strength>=3.5: rr=1.70
    else: rr=1.50
    return final,score,rr,{'originalSide':side,'override':reason,'position':pos,'chase':ch,'m15RSI':rsi,'m15DistATR':dist,'htfScore':htf,'ltfScore':ltf,'alignment':alignment,'structureAlignment':structure_align,'strength':strength}

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out.extend([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return sorted(out,key=lambda x:x['ts'])

def evaluate(side,en,sl,tp,cs):
    mfe=mae=0.0
    for i,x in enumerate(cs,1):
        if side=='BUY':mfe=max(mfe,x['high']-en);mae=max(mae,en-x['low']);hs=x['low']<=sl;ht=x['high']>=tp
        else:mfe=max(mfe,en-x['low']);mae=max(mae,x['high']-en);hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return {'result':'AMBIGUOUS','mfe':mfe,'mae':mae,'candles':i}
        if hs:return {'result':'SL','mfe':mfe,'mae':mae,'candles':i}
        if ht:return {'result':'TP','mfe':mfe,'mae':mae,'candles':i}
    return {'result':'UNRESOLVED','mfe':mfe,'mae':mae,'candles':len(cs)}

def run(label,cutoff):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);tmp=[];errs=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            _,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'en':fr['M5'][-1]['close'],'model':model,'f':core.features(sym,fr,su,bf)})
        except Exception as e:errs.append({'symbol':sym+'USDT','cutoff':cutoff,'error':str(e)})
    breadth=sum(r['f']['r24']>0 for r in tmp)/len(tmp) if tmp else .5;rows=[]
    for r in tmp:
        sym=r['sym'];side,score,rr,decision=decide(sym,r['f'],r['su'],r['model'],breadth);en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(sym)['stopBase'];recent=r['fr']['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk
        tp=en+rr*risk if side=='BUY' else en-rr*risk
        rows.append({'symbol':sym+'USDT','cutoff':cutoff,'source':r['source'],'blind':True,'decision':side,'score':round(score,3),'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'breadth':round(breadth,3),'features':r['f'],'decisionMeta':decision,'model':r['model'],'outcome':evaluate(side,en,sl,tp,future(r['source'],sym,cut))})
    rows+=errs;usable=[x for x in rows if x.get('decision')];resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')];w=[x for x in resolved if x['outcome']['result']=='TP'];l=[x for x in resolved if x['outcome']['result']=='SL'];total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    s={'label':label,'cutoff':cutoff,'isTrueBlind':True,'requested':len(v6.COINS),'marketTrades':len(usable),'dataErrors':len(errs),'resolved':len(resolved),'wins':len(w),'losses':len(l),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(w)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(breadth,3),'overrides':sum(bool(x.get('decisionMeta',{}).get('override')) for x in usable)}
    return {'summary':s,'tests':rows}

def main():
    samples={label:run(label,c) for label,c in CUTOFFS}
    p={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V19 locked forced-market: V17 multi-horizon momentum/structure core + exhaustion override at extreme H1 range location when M15/M5 stretch/sweep confirms + transition LTF conflict handling; 48 M15 structural SL with .75 profile ATR floor; RR 1.5 base, 1.7 aligned, 1.9 only strong trend, exhaustion 1.5-1.55; both cutoffs unseen before lock.','samples':samples}
    with open('data/blind_backtest_v19.json','w') as f:json.dump(p,f,indent=2)
    print(json.dumps({k:v['summary'] for k,v in samples.items()},indent=2))
if __name__=='__main__':main()
