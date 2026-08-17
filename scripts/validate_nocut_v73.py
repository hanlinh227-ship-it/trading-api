#!/usr/bin/env python3
import json,sys
P='data/nocut_intraday_allpass_v73.json'

def wr(method):
    for key in ('development','mayJul30Development','walkForwardMayJuly'):
        s=method.get(key)
        if not s:continue
        for k in ('wrAllTrades','wrAllSelected','wr'):
            if k in s:return float(s[k])
    raise KeyError('missing WR statistic')

def main():
    d=json.load(open(P,encoding='utf-8'));r=d['hardRules'];errors=[]
    if r.get('cutUsed') is not False:errors.append('CUT must be false')
    if r.get('noTradeAllowed') is not False:errors.append('NO TRADE must be false')
    if r.get('minimumTradesPerDay')!=1:errors.append('min trades/day must be 1')
    if r.get('maximumTradesPerDay')!=3:errors.append('max trades/day must be 3')
    if set(map(float,r.get('rrAllowed',[])))!={1.0,2.0}:errors.append('RR allowed must be {1,2}')
    for market,count in (('forex',28),('crypto',61)):
        block=d[market];syms=block['symbols']
        if len(syms)!=count:errors.append(f'{market} symbol count {len(syms)} != {count}')
        if block.get('passCount')!=count or not block.get('allPassed'):errors.append(f'{market} allPassed gate failed')
        for s,e in syms.items():
            m=e['method'];w=wr(m)
            if m.get('status')!='PASS':errors.append(f'{market}:{s} status != PASS')
            if w<80:errors.append(f'{market}:{s} WR {w}<80')
            # exact current passing configurations are RR1; accept RR2 if a later frozen map uses it.
            style=m.get('style')
            if style and float(style.get('rr',1.0)) not in (1.0,2.0):errors.append(f'{market}:{s} bad RR')
            for a in m.get('actions',[]):
                if float(a.get('rr',1.0)) not in (1.0,2.0):errors.append(f'{market}:{s} action bad RR')
    if errors:
        print(json.dumps({'ok':False,'errors':errors},indent=2));sys.exit(1)
    mins={market:min(wr(e['method']) for e in d[market]['symbols'].values()) for market in ('forex','crypto')}
    print(json.dumps({'ok':True,'forex':28,'crypto':61,'minWR':mins,'classification':d.get('classification')},indent=2))
if __name__=='__main__':main()
