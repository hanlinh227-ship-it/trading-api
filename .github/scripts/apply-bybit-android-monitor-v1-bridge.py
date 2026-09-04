from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'bybit-live-bridge/bybit_live_bridge.py'
s=p.read_text()

def repl(old,new):
    global s
    if old not in s:
        raise SystemExit('MISSING_PATTERN: '+old[:180])
    s=s.replace(old,new,1)

repl(
"import json, math, os, subprocess, threading, time, urllib.error, urllib.parse, urllib.request",
"import hashlib, hmac, json, math, os, subprocess, threading, time, urllib.error, urllib.parse, urllib.request"
)
repl(
"BYBIT_ALLOWED_METHODS=('GET','POST')\nCURL_BIN=",
"BYBIT_ALLOWED_METHODS=('GET','POST')\nTELEMETRY_API_KEY=(os.environ.get('BYBIT_AUTO_API_KEY') or os.environ.get('HYRO_BYBIT_LIVE_API_KEY') or os.environ.get('HYRO_BYBIT_API_KEY') or '').strip()\nTELEMETRY_API_SECRET=(os.environ.get('BYBIT_AUTO_API_SECRET') or os.environ.get('HYRO_BYBIT_LIVE_API_SECRET') or os.environ.get('HYRO_BYBIT_API_SECRET') or '').strip()\nTELEMETRY_RECV_WINDOW=str(max(5000,min(20000,int(os.environ.get('BYBIT_RECV_WINDOW_MS','10000')))))\nCURL_BIN="
)
insert=r'''

def _bybit_readonly_get(path,params=None,signed=True):
    params=dict(params or {})
    query=urllib.parse.urlencode([(str(k),str(v)) for k,v in params.items() if v is not None and str(v)!=''])
    if signed and not (TELEMETRY_API_KEY and TELEMETRY_API_SECRET):
        raise RuntimeError('BYBIT_TELEMETRY_CREDENTIALS_MISSING')
    last=None
    for base in BYBIT_BASES:
        headers={'accept':'application/json','user-agent':BROWSER_UA}
        if signed:
            ts=str(int(time.time()*1000));payload=ts+TELEMETRY_API_KEY+TELEMETRY_RECV_WINDOW+query
            sig=hmac.new(TELEMETRY_API_SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()
            headers.update({'X-BAPI-API-KEY':TELEMETRY_API_KEY,'X-BAPI-TIMESTAMP':ts,'X-BAPI-RECV-WINDOW':TELEMETRY_RECV_WINDOW,'X-BAPI-SIGN':sig})
        req=urllib.request.Request(base+path+(('?'+query) if query else ''),headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=25) as r:
                raw=r.read(4_000_000).decode(errors='replace');status=int(r.status)
        except urllib.error.HTTPError as e:
            raw=e.read(4_000_000).decode(errors='replace');status=int(e.code)
        except Exception as e:
            last=RuntimeError('BYBIT_TELEMETRY_UPSTREAM:'+str(e)[:180]);continue
        try:body=json.loads(raw)
        except Exception:body={'retCode':None,'retMsg':raw[:300]}
        if status==200 and int(body.get('retCode',-1))==0:return body
        last=RuntimeError('BYBIT_TELEMETRY_HTTP_'+str(status)+':'+str(body.get('retMsg') or '')[:180])
        if status not in (403,429):break
    raise last or RuntimeError('BYBIT_TELEMETRY_UPSTREAM_FAILED')

def _closed_pnl_rows(start_ms,end_ms):
    out=[];cursor=''
    for _ in range(4):
        q={'category':'linear','startTime':start_ms,'endTime':end_ms,'limit':100}
        if cursor:q['cursor']=cursor
        r=_bybit_readonly_get('/v5/position/closed-pnl',q,True);result=r.get('result') or {};rows=result.get('list') or [];out.extend(rows)
        nxt=str(result.get('nextPageCursor') or '')
        if not nxt or nxt==cursor:break
        cursor=nxt
    seen=set();dedup=[]
    for x in out:
        k=(str(x.get('orderId') or ''),str(x.get('updatedTime') or x.get('createdTime') or ''),str(x.get('symbol') or ''))
        if k in seen:continue
        seen.add(k);dedup.append(x)
    return dedup

def readonly_telemetry():
    started=time.perf_counter();now=int(time.time()*1000)
    wallet=_bybit_readonly_get('/v5/account/wallet-balance',{'accountType':'UNIFIED','coin':'USDT'},True)
    positions=_bybit_readonly_get('/v5/position/list',{'category':'linear','settleCoin':'USDT','limit':200},True)
    closed=_closed_pnl_rows(now-72*60*60*1000,now)
    acct=((wallet.get('result') or {}).get('list') or [{}])[0] or {};coin=next((x for x in (acct.get('coin') or []) if str(x.get('coin') or '')=='USDT'),{})
    pos=[]
    for x in ((positions.get('result') or {}).get('list') or []):
        try:size=float(x.get('size') or 0)
        except Exception:size=0.0
        if size<=0:continue
        def f(k):
            try:return float(x.get(k) or 0)
            except Exception:return 0.0
        pos.append({'symbol':str(x.get('symbol') or ''),'side':str(x.get('side') or ''),'size':size,'avgPrice':f('avgPrice'),'markPrice':f('markPrice'),'unrealisedPnl':f('unrealisedPnl'),'leverage':f('leverage'),'takeProfit':f('takeProfit'),'stopLoss':f('stopLoss'),'liqPrice':f('liqPrice'),'positionValue':f('positionValue'),'positionIM':f('positionIM'),'positionIdx':f('positionIdx')})
    def af(v):
        try:return float(v or 0)
        except Exception:return 0.0
    return {'ok':True,'readOnly':True,'authenticated':True,'source':'VPS_BYBIT_SIGNED_READONLY_TELEMETRY','secretScope':'VPS_ONLY','account':{'equity':af(acct.get('totalEquity') or coin.get('equity')),'balance':af(acct.get('totalWalletBalance') or coin.get('walletBalance')),'availableBalance':af(acct.get('totalAvailableBalance') or coin.get('availableToWithdraw'))},'positions':pos,'closedPnl':closed,'closedPnlLookbackHours':72,'bybitLatencyMs':round((time.perf_counter()-started)*1000,2),'fetchedAt':int(time.time()*1000)}

def ws_telemetry(snaps):
    now=int(time.time()*1000);ages=[];stale=[];connected=ready=fresh=0
    for symbol,x in snaps.items():
        if x.get('connected'):connected+=1
        if not x.get('ok'):continue
        ready+=1;d=x.get('data') or {};book=d.get('book') or {};trades=d.get('trades') or {};lb=int(book.get('updateTime') or 0);lt=int(trades.get('lastTradeTime') or trades.get('updateTime') or 0)
        age=max(now-lb if lb>0 else 999999,now-lt if lt>0 else 999999);ages.append(max(0,age))
        if age<=5000:fresh+=1
        else:stale.append({'symbol':symbol,'dataAgeMs':max(0,age)})
    ages.sort()
    def pct(q):
        if not ages:return None
        i=max(0,min(len(ages)-1,int(math.ceil(q*len(ages)))-1));return int(ages[i])
    min_connected=max(1,int(math.ceil(len(snaps)*.80)));min_fresh=max(1,int(math.ceil(len(snaps)*.75)))
    return {'healthy':connected>=min_connected and fresh>=min_fresh,'connectedCount':connected,'readyCount':ready,'freshCount':fresh,'totalCount':len(snaps),'p50DataAgeMs':pct(.50),'p95DataAgeMs':pct(.95),'maxDataAgeMs':int(max(ages)) if ages else None,'staleSymbols':sorted(stale,key=lambda x:x['dataAgeMs'],reverse=True)[:20],'freshThresholdMs':5000,'timestamp':now}
'''
repl("\nMICROS={s:Microstructure(s) for s in SYMBOLS}\n\ndef bybit_proxy(body):",insert+"\n\nMICROS={s:Microstructure(s) for s in SYMBOLS}\n\ndef bybit_proxy(body):")
repl(
"'dynamicWsDiscovery':AUTO_DISCOVER,'maxWsSymbols':MAX_WS_SYMBOLS,'microstructure':{'ready':DEFAULT_SYMBOL in ready,'connected':bool(snaps.get(DEFAULT_SYMBOL,{}).get('connected'))}",
"'dynamicWsDiscovery':AUTO_DISCOVER,'maxWsSymbols':MAX_WS_SYMBOLS,'wsTelemetry':ws_telemetry(snaps),'microstructure':{'ready':DEFAULT_SYMBOL in ready,'connected':bool(snaps.get(DEFAULT_SYMBOL,{}).get('connected'))}"
)
repl(
"        if u.path=='/bybit/microstructure':\n            if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})",
"        if u.path=='/bybit/telemetry':\n            if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})\n            try:return self.sendj(200,readonly_telemetry())\n            except Exception as e:return self.sendj(503,{'ok':False,'readOnly':True,'error':'BYBIT_TELEMETRY_FAILED','detail':str(e)[:240]})\n        if u.path=='/bybit/microstructure':\n            if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})"
)
p.write_text(s)
print('BYBIT_ANDROID_MONITOR_V1_BRIDGE_PATCHED')
