#!/usr/bin/env python3
"""BTC-only Bybit VPS bridge.

Single BTCUSDT VPS authority for signed private REST proxy, public WebSocket
microstructure and event-driven Worker wakeups. Market data and execution wakeups
share the same confirmed WS stream so there is no second market reader or strategy
scheduler. Reconnect backoff is transport-only, never a trading time gate.
"""
from __future__ import annotations
import json, math, os, subprocess, threading, time, urllib.error, urllib.parse, urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET=(os.environ.get('BYBIT_VPS_BRIDGE_SECRET') or os.environ.get('V11_AI_BRIDGE_SECRET') or '').strip()
HOST=os.environ.get('BYBIT_VPS_BRIDGE_HOST',os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1'))
PORT=int(os.environ.get('BYBIT_VPS_BRIDGE_PORT',os.environ.get('V11_AI_BRIDGE_PORT','8789')))
SYMBOL='BTCUSDT'
WS_URL=os.environ.get('BYBIT_PUBLIC_WS','wss://stream.bybit.com/v5/public/linear')
WORKER_URL=(os.environ.get('BYBIT_WORKER_URL') or 'https://trading-v77-scanner.hanlinh227.workers.dev').rstrip('/')
EVENT_ENABLED=str(os.environ.get('BYBIT_EVENT_DRIVER_ENABLED','true')).lower() in ('1','true','yes')
BYBIT_BASES=tuple(dict.fromkeys(x.rstrip('/') for x in [os.environ.get('BYBIT_API_BASE_URL','').strip(),'https://api.bybit.com','https://api.bytick.com'] if x.strip()))
BYBIT_ALLOWED_PREFIXES=('/v5/account/','/v5/position/','/v5/order/','/v5/market/')
BYBIT_ALLOWED_METHODS=('GET','POST')
CURL_BIN='/usr/bin/curl' if os.path.exists('/usr/bin/curl') else 'curl'
BROWSER_UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'

try:
    import websocket
except Exception:
    websocket=None

class Microstructure:
    def __init__(self):
        self.lock=threading.RLock(); self.bids={}; self.asks={}; self.trades=deque(maxlen=16000); self.liquidations=deque(maxlen=4000)
        self.last_book=0; self.last_trade=0; self.last_liq=0; self.last_error=None; self.connected=False; self.thread=None
        self.event_last_fingerprint=None; self.event_inflight=False; self.event_pending=False
        self.event_last_wake=0; self.event_last_success=0; self.event_last_error=None; self.event_last_result=None; self.event_last_http=0; self.event_transport='CURL_HTTP'
    @staticmethod
    def _imb(b,a): return (b-a)/(b+a) if b+a>0 else 0.0
    @staticmethod
    def _bucket(x,step): return int(round(float(x)/step)) if step>0 else int(round(float(x)))
    @staticmethod
    def _curl_q(s): return str(s).replace('\\','\\\\').replace('"','\\"').replace('\n',' ').replace('\r',' ')
    def start(self):
        if websocket is None:
            self.last_error='WEBSOCKET_CLIENT_NOT_INSTALLED'; return
        if self.thread and self.thread.is_alive(): return
        self.thread=threading.Thread(target=self._loop,name='bybit-btc-public-ws',daemon=True); self.thread.start()
    def _loop(self):
        while True:
            try:
                app=websocket.WebSocketApp(WS_URL,on_open=self._open,on_message=self._message,on_error=self._error,on_close=self._close)
                app.run_forever(ping_interval=20,ping_timeout=10)
            except Exception as e:
                self.last_error='WS_LOOP:'+str(e)[:240]
            self.connected=False; time.sleep(2)
    def _open(self,ws):
        self.connected=True; self.last_error=None
        ws.send(json.dumps({'op':'subscribe','args':[f'orderbook.50.{SYMBOL}',f'publicTrade.{SYMBOL}',f'allLiquidation.{SYMBOL}']}))
    def _error(self,_ws,e): self.last_error='WS:'+str(e)[:240]
    def _close(self,_ws,_code,_msg): self.connected=False
    def _trade_window_locked(self,window_ms,now):
        buy=sell=0.0; n=0; first=last=0.0
        for t,side,q,p in self.trades:
            if t<now-window_ms: continue
            if first<=0:first=p
            last=p; n+=1; v=q*p
            if side=='Buy': buy+=v
            elif side=='Sell': sell+=v
        total=buy+sell
        return {'buyNotional':buy,'sellNotional':sell,'totalNotional':total,'deltaNotional':buy-sell,'imbalance':self._imb(buy,sell),'trades':n,'priceChangeBps':((last-first)/first*10000 if first>0 and last>0 else 0.0)}
    def _trade_imbalance_locked(self,window_ms,now): return self._trade_window_locked(window_ms,now)['imbalance']
    def _event_fingerprint(self,topic):
        now=int(time.time()*1000)
        with self.lock:
            if not self.bids or not self.asks:return None
            bids=sorted(self.bids.items(),reverse=True)[:50]; asks=sorted(self.asks.items())[:50]
            bb,bs=bids[0]; ba,as_=asks[0]; mid=(bb+ba)/2
            def depth(rows,bps):return sum(p*q for p,q in rows if abs(p-mid)/mid*10000<=bps)
            b2,a2=depth(bids,2),depth(asks,2); b5,a5=depth(bids,5),depth(asks,5)
            i2=self._imb(b2,a2); i5=self._imb(b5,a5)
            f1=self._trade_imbalance_locked(1000,now); f3=self._trade_imbalance_locked(3000,now); f5=self._trade_imbalance_locked(5000,now); f15=self._trade_imbalance_locked(15000,now)
            micro=(ba*bs+bb*as_)/(bs+as_) if bs+as_>0 else mid
            mp=(micro-mid)/mid*10000 if mid>0 else 0
            return (self._bucket(mid,.5),self._bucket(i2,.04),self._bucket(i5,.05),self._bucket(f1,.06),self._bucket(f3,.05),self._bucket(f5,.05),self._bucket(f15,.05),self._bucket(mp,.01),str(topic).split('.')[0])
    def _curl_worker(self,reason):
        reason=self._curl_q(str(reason)[:120]); secret=self._curl_q(SECRET); url=self._curl_q(WORKER_URL+'/bybit/auto/run')
        cfg='\n'.join([
            f'url = "{url}"','request = "POST"','http1.1','silent','show-error','max-time = 35','connect-timeout = 8',
            f'user-agent = "{self._curl_q(BROWSER_UA)}"','header = "content-type: application/json"','header = "accept: application/json"',
            'header = "accept-language: en-US,en;q=0.9"','header = "cache-control: no-cache"',
            f'header = "x-action-key: {secret}"','header = "x-btc-trigger: VPS_WS_EVENT"',f'header = "x-btc-trigger-reason: {reason}"',
            'data = "{}"','write-out = "\\n__BTC_HTTP_STATUS__:%{http_code}"',''
        ])
        p=subprocess.run([CURL_BIN,'--config','-'],input=cfg,text=True,capture_output=True,timeout=40,check=False)
        text=(p.stdout or ''); marker='\n__BTC_HTTP_STATUS__:'
        if marker in text:
            raw,status=text.rsplit(marker,1)
            try:code=int(status.strip())
            except Exception:code=0
        else:raw=text;code=0
        if p.returncode!=0 and code==0:raise RuntimeError('CURL_'+str(p.returncode)+':'+str(p.stderr or '')[:220])
        return code,raw
    def _urllib_worker(self,reason):
        req=urllib.request.Request(WORKER_URL+'/bybit/auto/run',method='POST',data=b'{}',headers={
            'content-type':'application/json','accept':'application/json','accept-language':'en-US,en;q=0.9','cache-control':'no-cache','user-agent':BROWSER_UA,
            'x-action-key':SECRET,'x-btc-trigger':'VPS_WS_EVENT','x-btc-trigger-reason':str(reason)[:120]})
        try:
            with urllib.request.urlopen(req,timeout=35) as r:return int(r.status),r.read(1_000_000).decode(errors='replace')
        except urllib.error.HTTPError as e:return int(e.code),e.read(1_000_000).decode(errors='replace')
    def _wake_worker(self,reason):
        self.event_last_wake=int(time.time()*1000)
        try:
            try:
                code,raw=self._curl_worker(reason); self.event_transport='CURL_HTTP'
            except Exception as curl_error:
                code,raw=self._urllib_worker(reason); self.event_transport='URLLIB_FALLBACK'
                if code==0:raise curl_error
            self.event_last_http=int(code)
            try:out=json.loads(raw)
            except Exception:out={'raw':str(raw)[:500]}
            self.event_last_result=out
            if self.event_last_http==200 and out.get('ok') is not False:
                self.event_last_success=int(time.time()*1000); self.event_last_error=None
            else:
                self.event_last_error=f'WORKER_HTTP_{self.event_last_http}:'+str(out)[:240]
                print('BTC_EVENT_WAKE_ERROR',self.event_last_error,flush=True)
        except Exception as e:
            self.event_last_http=0; self.event_last_error='WORKER_WAKE:'+str(e)[:240]
            print('BTC_EVENT_WAKE_ERROR',self.event_last_error,flush=True)
        finally:
            with self.lock:
                rerun=self.event_pending; self.event_pending=False
                if not rerun:self.event_inflight=False
            if rerun:self._spawn_wake('COALESCED_LATEST_STATE')
    def _spawn_wake(self,reason):
        if not EVENT_ENABLED or not SECRET:return
        with self.lock:
            if self.event_inflight:
                self.event_pending=True; return
            self.event_inflight=True
        threading.Thread(target=self._wake_worker,args=(reason,),name='btc-worker-wake',daemon=True).start()
    def _maybe_wake(self,topic):
        fp=self._event_fingerprint(topic)
        if fp is None:return
        with self.lock:
            if fp==self.event_last_fingerprint:return
            self.event_last_fingerprint=fp
        self._spawn_wake('MARKET_STATE_CHANGE:'+str(topic))
    def _message(self,_ws,raw):
        try: msg=json.loads(raw)
        except Exception: return
        topic=str(msg.get('topic') or ''); data=msg.get('data') or {}; now=int(time.time()*1000); changed=False
        with self.lock:
            if topic.startswith('orderbook.'):
                if msg.get('type')=='snapshot': self.bids={float(p):float(q) for p,q in data.get('b',[]) if float(q)>0}; self.asks={float(p):float(q) for p,q in data.get('a',[]) if float(q)>0}
                else:
                    for p,q in data.get('b',[]):
                        p=float(p);q=float(q); self.bids.pop(p,None) if q==0 else self.bids.__setitem__(p,q)
                    for p,q in data.get('a',[]):
                        p=float(p);q=float(q); self.asks.pop(p,None) if q==0 else self.asks.__setitem__(p,q)
                self.last_book=int(msg.get('cts') or msg.get('ts') or now); changed=True
            elif topic==f'publicTrade.{SYMBOL}':
                for x in (data if isinstance(data,list) else [data]):
                    try:self.trades.append((int(x.get('T') or now),str(x.get('S') or ''),float(x.get('v') or 0),float(x.get('p') or 0))); changed=True
                    except Exception:pass
                self.last_trade=int(msg.get('ts') or now)
            elif topic==f'allLiquidation.{SYMBOL}':
                for x in (data if isinstance(data,list) else [data]):
                    try:self.liquidations.append((int(x.get('T') or now),str(x.get('S') or ''),float(x.get('v') or 0),float(x.get('p') or 0))); changed=True
                    except Exception:pass
                self.last_liq=int(msg.get('ts') or now)
        if changed:self._maybe_wake(topic)
    def event_status(self):
        with self.lock:
            r=self.event_last_result or {}; ctl=r.get('controller') or {}
            return {'integrated':True,'enabled':EVENT_ENABLED,'authority':'VPS_WS_MARKET_STATE_CHANGE','transport':self.event_transport,'inflight':self.event_inflight,'pending':self.event_pending,'lastWakeAt':self.event_last_wake,'lastSuccessAt':self.event_last_success,'lastHttpStatus':self.event_last_http,'lastError':self.event_last_error,'lastResultMode':r.get('mode') or ctl.get('executionMode'),'lastResultReason':r.get('reason') or ctl.get('lastCycleReason')}
    def snapshot(self):
        now=int(time.time()*1000)
        with self.lock:
            bids=sorted(self.bids.items(),reverse=True)[:50]; asks=sorted(self.asks.items())[:50]; trades=list(self.trades); liqs=list(self.liquidations); lb=self.last_book; lt=self.last_trade; ll=self.last_liq; connected=self.connected; err=self.last_error
        if not bids or not asks:return {'ok':False,'reason':'BOOK_NOT_READY','connected':connected,'error':err,'at':now}
        bb,bs=bids[0]; ba,as_=asks[0]; mid=(bb+ba)/2
        last_trade_price=trades[-1][3] if trades else 0.0
        last_trade_side=trades[-1][1] if trades else ''
        last_trade_time=trades[-1][0] if trades else lt
        def depth(rows,bps):return sum(p*q for p,q in rows if abs(p-mid)/mid*10000<=bps)
        def weighted(rows):return sum(p*q*math.exp(-(abs(p-mid)/mid*10000)/4) for p,q in rows)
        b2,a2=depth(bids,2),depth(asks,2); b5,a5=depth(bids,5),depth(asks,5); b10,a10=depth(bids,10),depth(asks,10); wb,wa=weighted(bids),weighted(asks)
        micro=(ba*bs+bb*as_)/(bs+as_) if bs+as_>0 else mid
        with self.lock:
            w1=self._trade_window_locked(1000,now); w3=self._trade_window_locked(3000,now); w5=self._trade_window_locked(5000,now); w15=self._trade_window_locked(15000,now); w60=self._trade_window_locked(60000,now)
        base1=max(w60['totalNotional']/60,1.0); base3=max(w60['totalNotional']/20,1.0); base5=max(w60['totalNotional']/12,1.0)
        long_usd=short_usd=0.0; events=0
        for t,side,q,p in liqs:
            if t<now-60000:continue
            events+=1; v=q*p
            if side=='Buy':long_usd+=v
            elif side=='Sell':short_usd+=v
        total_liq=long_usd+short_usd
        return {'ok':True,'data':{'symbol':SYMBOL,'at':now,'source':'VPS_BYBIT_WS','book':{'bestBid':bb,'bestAsk':ba,'mid':mid,'spreadBps':(ba-bb)/mid*10000,'microprice':micro,'micropriceEdgeBps':(micro-mid)/mid*10000,'bidDepth2':b2,'askDepth2':a2,'bidDepth5':b5,'askDepth5':a5,'bidDepth10':b10,'askDepth10':a10,'imbalance2':self._imb(b2,a2),'imbalance5':self._imb(b5,a5),'imbalance10':self._imb(b10,a10),'imbalance':self._imb(wb,wa),'updateTime':lb},'trades':{'lastPrice':last_trade_price,'lastTradeSide':last_trade_side,'lastTradeTime':last_trade_time,'aggressorImbalance':w15['imbalance'],'deltaNotional':w15['deltaNotional'],'notional15s':w15['totalNotional'],'notional60s':w60['totalNotional'],'burst1x':w1['totalNotional']/base1,'burst3x':w3['totalNotional']/base3,'burst5x':w5['totalNotional']/base5,'priceChange1sBps':w1['priceChangeBps'],'priceChange3sBps':w3['priceChangeBps'],'priceChange5sBps':w5['priceChangeBps'],'window1s':w1,'window3s':w3,'window5s':w5,'window15s':w15,'window60s':w60,'updateTime':lt},'liquidations':{'longLiquidationUsd':long_usd,'shortLiquidationUsd':short_usd,'totalUsd':total_liq,'imbalance':self._imb(long_usd,short_usd),'events':events,'updateTime':ll}},'connected':connected,'error':err,'eventDriver':self.event_status()}

MICRO=Microstructure()

def bybit_proxy(body):
    method=str(body.get('method') or '').upper(); path=str(body.get('path') or ''); query=str(body.get('query') or ''); raw=str(body.get('body') or ''); headers=body.get('headers') or {}
    if method not in BYBIT_ALLOWED_METHODS:return 405,{'ok':False,'error':'BYBIT_METHOD_NOT_ALLOWED','transport':'VPS_BYBIT_PRIVATE_PROXY'}
    if not path.startswith(BYBIT_ALLOWED_PREFIXES):return 403,{'ok':False,'error':'BYBIT_PATH_NOT_ALLOWED','path':path,'transport':'VPS_BYBIT_PRIVATE_PROXY'}
    safe_headers={k:str(v) for k,v in headers.items() if str(k).lower() in ('x-bapi-api-key','x-bapi-timestamp','x-bapi-recv-window','x-bapi-sign','content-type','accept','x-trading-runtime-contract')}
    lower={x.lower() for x in safe_headers}
    if not all(k in lower for k in ('x-bapi-api-key','x-bapi-timestamp','x-bapi-recv-window','x-bapi-sign')):return 400,{'ok':False,'error':'BYBIT_SIGNED_HEADERS_MISSING','transport':'VPS_BYBIT_PRIVATE_PROXY'}
    attempts=[];last_status=502;last_body=None
    for base in BYBIT_BASES:
        attempts.append(base);url=base+path+(('?'+query) if method=='GET' and query else '');data=None if method=='GET' else raw.encode();req=urllib.request.Request(url,data=data,method=method,headers=safe_headers)
        try:
            with urllib.request.urlopen(req,timeout=25) as r:status=r.status;txt=r.read(2_000_000).decode(errors='replace')
        except urllib.error.HTTPError as e:status=e.code;txt=e.read(2_000_000).decode(errors='replace')
        except Exception as e:last_status=502;last_body={'retCode':None,'retMsg':'UPSTREAM_FETCH_FAILED:'+str(e)[:180]};continue
        try:payload=json.loads(txt)
        except Exception:payload={'retCode':None,'retMsg':txt[:300] or ('HTTP_'+str(status))}
        last_status=status;last_body=payload
        if status not in (403,429):return 200,{'ok':200<=status<300 and int(payload.get('retCode',-1))==0,'httpStatus':status,'upstream':payload,'base':base,'attempts':attempts,'transport':'VPS_BYBIT_PRIVATE_PROXY'}
    return 200,{'ok':False,'httpStatus':last_status,'upstream':last_body,'base':attempts[-1] if attempts else None,'attempts':attempts,'transport':'VPS_BYBIT_PRIVATE_PROXY'}

class Handler(BaseHTTPRequestHandler):
    def sendj(self,code,obj):
        b=json.dumps(obj,separators=(',',':')).encode();self.send_response(code);self.send_header('content-type','application/json');self.send_header('cache-control','no-store');self.send_header('content-length',str(len(b)));self.end_headers();self.wfile.write(b)
    def authorized(self):return bool(SECRET) and self.headers.get('authorization','')=='Bearer '+SECRET
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/health':
            snap=MICRO.snapshot();return self.sendj(200,{'ok':True,'service':'BYBIT_BTC_LIVE_BRIDGE','privateProxy':True,'microstructure':{'ready':bool(snap.get('ok')),'connected':bool(snap.get('connected')),'reason':snap.get('reason'),'error':snap.get('error')},'eventDriver':MICRO.event_status(),'legacyAiCouncil':False,'forex':False,'meme':False,'timestamp':int(time.time()*1000)})
        if u.path=='/bybit/microstructure':
            if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
            q=urllib.parse.parse_qs(u.query);symbol=str((q.get('symbol') or [SYMBOL])[0]).upper()
            if symbol!=SYMBOL:return self.sendj(400,{'ok':False,'error':'BTCUSDT_ONLY'})
            snap=MICRO.snapshot();return self.sendj(200 if snap.get('ok') else 503,snap)
        return self.sendj(404,{'ok':False,'error':'NOT_FOUND'})
    def do_POST(self):
        if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
        try:n=int(self.headers.get('content-length','0'));body=json.loads(self.rfile.read(n) or b'{}')
        except Exception:return self.sendj(400,{'ok':False,'error':'BAD_JSON'})
        if self.path=='/bybit/private':code,out=bybit_proxy(body);return self.sendj(code,out)
        return self.sendj(404,{'ok':False,'error':'NOT_FOUND'})
    def log_message(self,*_):pass

def main():
    if not SECRET:raise SystemExit('BYBIT_VPS_BRIDGE_SECRET_OR_V11_AI_BRIDGE_SECRET_REQUIRED')
    MICRO.start();ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
if __name__=='__main__':main()
