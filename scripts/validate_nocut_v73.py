#!/usr/bin/env python3
import json,sys
P='data/nocut_intraday_allpass_v73.json'

def stats(method):
    for key in ('development','mayJul30Development','walkForwardMayJuly'):
        s=method.get(key)
        if s:return s
    raise KeyError('missing development statistic')

def wr(method):
    s=stats(method)
    for k in ('wrAllTrades','wrAllSelected','wr'):
        if k in s:return float(s[k])
    raise KeyError('missing WR statistic')

def router_action_refs(node):
    if not node:return set()
    kind=node.get('kind')
    if kind=='leaf':return {node['action']}
    if kind=='root':return router_action_refs(node['lo']) | router_action_refs(node['hi'])
    if kind=='split':
        if 'loAction' in node:return {node['loAction'],node['hiAction']}
        return router_action_refs(node['lo']) | router_action_refs(node['hi'])
    raise ValueError(f'unknown router node kind {kind}')

def main():
    d=json.load(open(P,encoding='utf-8'));r=d['hardRules'];errors=[]
    if d.get('classification')!='EXPOSED DEVELOPMENT ALL-PASS; NOT UNTOUCHED OOS':errors.append('integrity classification changed')
    if r.get('cutUsed') is not False:errors.append('CUT must be false')
    if r.get('noTradeAllowed') is not False:errors.append('NO TRADE must be false')
    if r.get('minimumTradesPerDay')!=1:errors.append('min trades/day must be 1')
    if r.get('maximumTradesPerDay')!=3:errors.append('max trades/day must be 3')
    if set(map(float,r.get('rrAllowed',[])))!={1.0,2.0}:errors.append('RR allowed must be {1,2}')
    for market,count in (('forex',28),('crypto',61)):
        block=d[market];syms=block['symbols']
        if len(syms)!=count:errors.append(f'{market} symbol count {len(syms)} != {count}')
        if block.get('passCount')!=count or not block.get('allPassed'):errors.append(f'{market} allPassed gate failed')
        for sym,e in syms.items():
            m=e['method'];s=stats(m);w=wr(m)
            if m.get('status')!='PASS':errors.append(f'{market}:{sym} status != PASS')
            if w<80:errors.append(f'{market}:{sym} WR {w}<80')
            if int(s.get('trades',-1))!=int(s.get('expectedDays',-2)):errors.append(f'{market}:{sym} frozen map is not exactly 1 trade/day')
            if not e.get('newsProfile'):errors.append(f'{market}:{sym} missing newsProfile')
            tf=e.get('timeframe')
            if market=='forex' and tf!='H1':errors.append(f'forex:{sym} timeframe must be H1')
            if market=='crypto' and tf not in ('H1','4H'):errors.append(f'crypto:{sym} unsupported timeframe {tf}')
            style=m.get('style')
            if style and float(style.get('rr',1.0)) not in (1.0,2.0):errors.append(f'{market}:{sym} bad RR')
            actions=m.get('actions',[]);ids=set()
            for a in actions:
                if a.get('id') in ids:errors.append(f'{market}:{sym} duplicate action id {a.get("id")}')
                ids.add(a.get('id'))
                if float(a.get('rr',1.0)) not in (1.0,2.0):errors.append(f'{market}:{sym} action bad RR')
            if m.get('router'):
                try:refs=router_action_refs(m['router'])
                except Exception as ex:errors.append(f'{market}:{sym} invalid router: {ex}');refs=set()
                missing=refs-ids
                if missing:errors.append(f'{market}:{sym} router references missing actions {sorted(missing)}')
    if errors:
        print(json.dumps({'ok':False,'errors':errors},indent=2));sys.exit(1)
    mins={market:min(wr(e['method']) for e in d[market]['symbols'].values()) for market in ('forex','crypto')}
    routed=sum(1 for market in ('forex','crypto') for e in d[market]['symbols'].values() if e['method'].get('router'))
    print(json.dumps({'ok':True,'forex':28,'crypto':61,'minWR':mins,'exactlyOneTradePerDay':True,'newsProfiles':89,'routedSymbols':routed,'classification':d.get('classification')},indent=2))
if __name__=='__main__':main()
