#!/usr/bin/env python3
"""BTC-only Bybit VPS bridge.

Preserves the existing signed private REST proxy contract used by the Cloudflare Worker
and adds an optional event-driven public microstructure collector for BTCUSDT.
No AI council, Forex bot, Meme bot or strategy decision runs here.
"""
from __future__ import annotations
import json, math, os, threading, time, urllib.error, urllib.parse, urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET=(os.environ.get('BYBIT_VPS_BRIDGE_SECRET') or os.environ.get('V11_AI_BRIDGE_SECRET') or '').strip()
HOST=os.environ.get('BYBIT_VPS_BRIDGE_HOST',os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1'))
PORT=int(os.environ.get('BYBIT_VPS_BRIDGE_PORT',os.environ.get('V11_AI_BRIDGE_PORT','8789')))
SYMBOL='BTCUSDT'
WS_URL=os.environ.get('BYBIT_PUBLIC_WS','wss://stream.bybit.com/v5/public/linear')
BYBIT_BASES=tuple(dict.fromkeys(x.rstrip('/') for x in [os.environ.get('BYBIT_API_BASE_URL','').strip(),'https://api.bybit.com','https://api.bytick.com'] if x.strip()))
BYBIT_ALLOWED_PREFIXES=('/v5/account/','/v5/position/','/v5/order/','/v5/market/')
BYBIT_ALLOWED_METHODS=('GET','POST')

try:
    import websocket  # websocket-client
except Exception:
    websocket=None

class Microstructure:
    def __init__(self):
        self.lock=threading.RLock(); self.bids={}; self.asks={}; self.trades=deque(maxlen=12000); self.liquidations=deque(maxlen=4000)
        self.last_book=0; self.last_trade=0; self.last_liq=0; self.last_error=None; self.connected=False; self.thread=None
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
    def _message(self,_ws,raw):
        try: msg=json.loads(raw)
        except Exception: return
        topic=str(msg.get('topic') or ''); data=msg.get('data') or {}; now=int(time.time()*1000)
        with self.lock:
            if topic.startswith('orderbook.'):
                if msg.get('type')=='snapshot': self.bids={float(p):float(q) for p,q in data.get('b',[]) if float(q)>0}; self.asks={float(p):float(q) for p,q in data.get('a',[]) if float(q)>0}
                else:
                    for p,q in data.get('b',[]):
                        p=float(p);q=float(q); self.bids.pop(p,None) if q==0 else self.bids.__setitem__(p,q)
                    for p,q in data.get('a',[]):
                        p=float(p);q=float(q); self.asks.pop(p,None) if q==0 else self.asks.__setitem__(p,q)
                self.last_book=int(msg.get('cts') or msg.get('ts') or now)
            elif topic==f'publicTrade.{SYMBOL}':
                for x in (data if isinstance(data,list) else [data]):
                    try:self.trades.append((int(x.get('T') or now),str(x.get('S') or ''),float(x.get('v') or 0),float(x.get('p') or 0)))
                    except Exception:pass
                self.last_trade=int(msg.get('ts') or now)
            elif topic==f'allLiquidation.{SYMBOL}':
                for x in (data if isinstance(data,list) else [data]):
                    try:self.liquidations.append((int(x.get('T') or now),str(x.get('S') or ''),float(x.get('v') or 0),float(x.get('p') or 0)))
                    except Exception:pass
                self.last_liq=int(msg.get('ts') or now)
    @staticmethod
    def _imb(b,a): return (b-a)/(b+a) if b+a>0 else 0.0
    def snapshot(self):
        now=int(time.time()*1000)
        with self.lock:
            bids=sorted(self.bids.items(),reverse=True)[:50]; asks=sorted(self.asks.items())[:50]; trades=list(self.trades); liqs=list(self.liquidations); lb=self.last_book; lt=self.last_trade; ll=self.last_liq; connected=self.connected; err=self.last_error
        if not bids or not asks:return {'ok':False,'reason':'BOOK_NOT_READY','connected':connected,'error':err,'at':now}
        bb,bs=bids[0]; ba,as_=asks[0]; mid=(bb+ba)/2
        def depth(rows,bps):return sum(p*q for p,q in rows if abs(p-mid)/mid*10000<=bps)
        def weighted(rows):return sum(p*q*math.exp(-(abs(p-mid)/mid*10000)/4) for p,q in rows)
        b2,a2=depth(bids,2),depth(asks,2); b5,a5=depth(bids,5),depth(asks,5); b10,a10=depth(bids,10),depth(asks,10); wb,wa=weighted(bids),weighted(asks)
        micro=(ba*bs+bb*as_)/(bs+as_) if bs+as_>0 else mid
        def t_window(ms):
            buy=sell=0.0; n=0
            for t,side,q,p in trades:
                if t<now-ms:continue
                v=q*p;n+=1
                if side=='Buy':buy+=v
                elif side=='Sell':sell+=v
            total=buy+sell;return {'buyNotional':buy,'sellNotional':sell,'totalNotional':total,'deltaNotional':buy-sell,'imbalance':self._imb(buy,sell),'trades':n}
        w5,w15,w60=t_window(5000),t_window(15000),t_window(60000); base=max(w60['totalNotional']/12,1.0)
        long_usd=short_usd=0.0; events=0
        for t,side,q,p in liqs:
            if t<now-60000:continue
            events+=1; v=q*p
            if side=='Buy':long_usd+=v
            elif side=='Sell':short_usd+=v
        total_liq=long_usd+short_usd
        return {'ok':True,'data':{'symbol':SYMBOL,'at':now,'source':'VPS_BYBIT_WS','book':{'bestBid':bb,'bestAsk':ba,'mid':mid,'spreadBps':(ba-bb)/mid*10000,'microprice':micro,'micropriceEdgeBps':(micro-mid)/mid*10000,'bidDepth2':b2,'askDepth2':a2,'bidDepth5':b5,'askDepth5':a5,'bidDepth10':b10,'askDepth10':a10,'imbalance2':self._imb(b2,a2),'imbalance5':self._imb(b5,a5),'imbalance10':self._imb(b10,a10),'imbalance':self._imb(wb,wa),'updateTime':lb},'trades':{'aggressorImbalance':w15['imbalance'],'deltaNotional':w15['deltaNotional'],'notional15s':w15['totalNotional'],'notional60s':w60['totalNotional'],'burst5x':w5['totalNotional']/base,'window5s':w5,'window15s':w15,'window60s':w60,'updateTime':lt},'liquidations':{'longLiquidationUsd':long_usd,'shortLiquidationUsd':short_usd,'totalUsd':total_liq,'imbalance':self._imb(long_usd,short_usd),'events':events,'updateTime':ll}},'connected':connected,'error':err}

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
            snap=MICRO.snapshot();return self.sendj(200,{'ok':True,'service':'BYBIT_BTC_LIVE_BRIDGE','privateProxy':True,'microstructure':{'ready':bool(snap.get('ok')),'connected':bool(snap.get('connected')),'reason':snap.get('reason'),'error':snap.get('error')},'legacyAiCouncil':False,'forex':False,'meme':False,'timestamp':int(time.time()*1000)})
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
