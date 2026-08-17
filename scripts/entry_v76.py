#!/usr/bin/env python3
"""V76 live Forex entry gate.
Reads V75 status + locked V76 methods. It never fetches market data itself.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import research_v76_entry_forex as r

VERSION='V76-ENTRY-LIVE-R1'

def pdt(s):
    d=datetime.fromisoformat(str(s).replace('Z','+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
def rows(frame):
    out=[]
    for x in (frame or {}).get('candles') or []:
        try:out.append([int(pdt(x[0]).timestamp()),float(x[1]),float(x[2]),float(x[3]),float(x[4]),x[5] if len(x)>5 else None])
        except Exception:pass
    return out

def detect(status,method):
    fs=status.get('frames') or {};m5r=rows(fs.get('M5'));m15r=rows(fs.get('M15'))
    if len(m5r)<15 or len(m15r)<15:return None,'INSUFFICIENT_COMPACT_BARS'
    m5=r.enrich(m5r,300);m15=r.enrich(m15r,900);i=len(m5r)-1;j=len(m15r)-1;arch=method['archetype']
    h1=((fs.get('H1') or {}).get('summary') or {});hc=h1.get('close');he20=h1.get('ema20');he50=h1.get('ema50')
    h1side='LONG' if None not in (hc,he20,he50) and hc>he20>he50 else 'SHORT' if None not in (hc,he20,he50) and hc<he20<he50 else 'NEUTRAL'
    def mk(side,level,structure,z=None):return {'side':side,'level':level,'structure':structure,'fvg':z,'signalClose':m5r[-1][4],'atr':m5.atr14[i]}
    if arch in ('A_SWEEP_MSS','C_SWEEP_FVG'):
        for jj in range(j,max(7,j-2),-1):
            for side,lv,ext in r.m15_sweeps(m15,jj):
                if (m15r[-1][0]+900)-(m15r[jj][0]+900)>1800:continue
                disp=r.displacement(m5,i,side);z=r.fvg_at(m5,i,side)
                if arch=='A_SWEEP_MSS' and disp is not None:return mk(side,disp,ext,z),None
                if arch=='C_SWEEP_FVG' and z is not None:return mk(side,sum(z)/2,ext,z),None
        return None,'SETUP_NOT_PRESENT'
    if arch=='B_H1_PULLBACK_RECLAIM':
        if h1side=='NEUTRAL' or m15.ema20[j] is None:return None,'H1_OR_M15_NOT_READY'
        side=h1side;bar=m15r[-1];e=m15.ema20[j];ok=(side=='LONG' and bar[3]<=e<bar[4]) or (side=='SHORT' and bar[2]>=e>bar[4]);disp=r.displacement(m5,i,side)
        if ok and disp is not None:return mk(side,disp,min(x[3] for x in m5r[-10:]) if side=='LONG' else max(x[2] for x in m5r[-10:]),r.fvg_at(m5,i,side)),None
        return None,'SETUP_NOT_PRESENT'
    if arch=='D_BREAK_RETEST_CONT':
        if h1side=='NEUTRAL' or j<13:return None,'H1_OR_M15_NOT_READY'
        side=h1side;cur=m15r[-1]
        for k in range(j-1,max(11,j-5),-1):
            prev=m15r[k-12:k];a=m15.atr14[k]
            if a is None:continue
            hi=max(x[2] for x in prev);lo=min(x[3] for x in prev);b=m15r[k];lv=hi if side=='LONG' else lo
            broke=b[4]>hi+.05*a if side=='LONG' else b[4]<lo-.05*a;retest=cur[3]<=lv<cur[4] if side=='LONG' else cur[2]>=lv>cur[4];disp=r.displacement(m5,i,side)
            if broke and retest and disp is not None:return mk(side,lv,min(x[3] for x in m5r[-12:]) if side=='LONG' else max(x[2] for x in m5r[-12:]),r.fvg_at(m5,i,side)),None
        return None,'SETUP_NOT_PRESENT'
    if arch=='E_FAILED_BREAK_REV':
        for k in range(j,max(11,j-3),-1):
            prev=m15r[k-12:k];a=m15.atr14[k]
            if a is None:continue
            hi=max(x[2] for x in prev);lo=min(x[3] for x in prev);mid=(hi+lo)/2;b=m15r[k];tests=[]
            if b[2]>hi+.15*a and b[4]<hi and b[4]<mid:tests.append(('SHORT',b[2]))
            if b[3]<lo-.15*a and b[4]>lo and b[4]>mid:tests.append(('LONG',b[3]))
            for side,ext in tests:
                disp=r.displacement(m5,i,side)
                if disp is not None:return mk(side,disp,ext,r.fvg_at(m5,i,side)),None
        return None,'SETUP_NOT_PRESENT'
    if arch=='F_IFVG_RECLAIM':
        for side in ('LONG','SHORT'):
            z=r.opposite_gap(m5,i,side);disp=r.displacement(m5,i,side)
            if z and disp is not None and ((side=='LONG' and m5r[-1][4]>z[1]) or (side=='SHORT' and m5r[-1][4]<z[0])):
                return mk(side,sum(z)/2,min(x[3] for x in m5r[-10:]) if side=='LONG' else max(x[2] for x in m5r[-10:]),z),None
        return None,'SETUP_NOT_PRESENT'
    return None,'UNKNOWN_ARCHETYPE'

def plan(status,method,venue_bid=None,venue_ask=None,venue_ts=None,news_clear=False):
    if not method.get('liveEligible'):return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':'NO_ENTRY','reason':'METHOD_NOT_OOS_PROMOTED','method':method}
    sig,err=detect(status,method)
    if not sig:return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':'NO_ENTRY','reason':err,'method':{k:method.get(k) for k in ('archetype','entryMode','stopMode','rr')}}
    side=sig['side'];atr=sig['atr'];px=status.get('currentPrice')
    if None in (atr,px) or atr<=0:return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':'NO_ENTRY','reason':'PRICE_OR_ATR_MISSING'}
    px=float(px);mode=method['entryMode'];intent='MARKET';entry=px
    if mode=='CLOSE':
        if abs(px-sig['signalClose'])>.35*atr:return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':'NO_ENTRY','reason':'CHASE_TOO_FAR_FROM_SIGNAL_CLOSE'}
    elif mode=='RETEST':
        lv=float(sig['level'])
        if abs(px-lv)<=.15*atr:entry=px
        else:intent='LIMIT';entry=lv
    else:
        if not sig.get('fvg'):return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':'NO_ENTRY','reason':'FVG_ZONE_MISSING'}
        intent='LIMIT';entry=sum(sig['fvg'])/2
    st=float(sig['structure']);raw=st-.05*atr if side=='LONG' else st+.05*atr;dist=entry-raw if side=='LONG' else raw-entry
    if dist<=0:return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':'NO_ENTRY','reason':'INVALID_STRUCTURE_STOP'}
    if method['stopMode']=='STRUCTURE_ATR' and dist<.8*atr:dist=.8*atr
    sl=entry-dist if side=='LONG' else entry+dist;rr=int(method['rr']);tp=entry+rr*dist if side=='LONG' else entry-rr*dist
    h1=((status.get('frames') or {}).get('H1') or {}).get('summary') or {};opp=h1.get('recent50High') if side=='LONG' else h1.get('recent50Low');room=None
    if opp is not None:room=(float(opp)-entry)/dist if side=='LONG' else (entry-float(opp))/dist
    if rr==2 and (room is None or room<2.2):return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':'NO_ENTRY','reason':'RR2_ROOM_LT_2_2R','roomR':room}
    executable=False;venue={}
    if venue_bid is not None and venue_ask is not None and venue_ts:
        age=(datetime.now(timezone.utc)-pdt(venue_ts).astimezone(timezone.utc)).total_seconds();spread=float(venue_ask)-float(venue_bid);mid=(float(venue_ask)+float(venue_bid))/2;spread_r=spread/dist if dist else 99
        executable=age<=30 and spread>=0 and spread_r<=.10;venue={'bid':venue_bid,'ask':venue_ask,'timestamp':venue_ts,'ageSeconds':round(age,3),'spreadR':round(spread_r,4),'mid':mid}
    action=intent if executable and news_clear else 'NO_ENTRY';reason=None if action!='NO_ENTRY' else 'NEWS_CHECK_REQUIRED' if executable and not news_clear else 'VENUE_CONFIRMATION_REQUIRED'
    return {'version':VERSION,'symbol':status.get('requestedSymbol'),'action':action,'reason':reason,'technicalIntent':intent,'side':side,'entry':entry,'sl':sl,'tp':tp,'rr':rr,'riskDistance':dist,'roomR':room,'newsClear':news_clear,'venue':venue,'method':{k:method.get(k) for k in ('archetype','entryMode','stopMode','rr')},'evidence':{'validation':method.get('validation'),'oos':method.get('oos')}}

def validate(methods):
    assert methods.get('selectionFrozen') is True and methods.get('selectionData')=='DEV_PLUS_VALIDATION_ONLY' and methods.get('oosUsedFor')=='PROMOTION_GATE_ONLY'
    mm=methods.get('methods') or {};assert set(mm)==set(r.PAIRS)
    for m in mm.values():
        assert m.get('archetype') in r.SETUP_DEFS and m.get('entryMode') in r.ENTRY_MODES and m.get('stopMode') in r.STOP_MODES and m.get('rr') in r.RR_VALUES
    print(json.dumps({'version':VERSION,'pairs':len(mm),'retained':methods.get('retainedArchetypes'),'validation':'PASS'}))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('status',nargs='?',default='data/status.json');ap.add_argument('--methods',default='data/v76_entry_methods.json');ap.add_argument('--venue-bid',type=float);ap.add_argument('--venue-ask',type=float);ap.add_argument('--venue-ts');ap.add_argument('--news-clear',action='store_true');ap.add_argument('--validate',action='store_true');a=ap.parse_args();methods=json.load(open(a.methods,encoding='utf-8'))
    if a.validate:return validate(methods)
    status=json.load(open(a.status,encoding='utf-8'));sym=status.get('requestedSymbol') or status.get('symbol');method=(methods.get('methods') or {}).get(sym)
    if not method:print(json.dumps({'version':VERSION,'symbol':sym,'action':'NO_ENTRY','reason':'NO_V76_METHOD'}));return
    print(json.dumps(plan(status,method,a.venue_bid,a.venue_ask,a.venue_ts,a.news_clear),ensure_ascii=False,separators=(',',':')))
if __name__=='__main__':main()
