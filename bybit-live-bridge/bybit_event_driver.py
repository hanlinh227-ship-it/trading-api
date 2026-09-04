#!/usr/bin/env python3
"""Autonomous BTCUSDT event driver.

Consumes Bybit public WebSocket events and wakes the deterministic BTC engine whenever
market state materially changes. There is no session window, strategy timer, cooldown,
trade quota, or timed entry gate. Reconnect backoff is transport-only and never a trading rule.
"""
from __future__ import annotations
import json, math, os, threading, urllib.request
from collections import deque

try:
    import websocket
except Exception:
    websocket=None

SYMBOL='BTCUSDT'
WS_URL=os.environ.get('BYBIT_PUBLIC_WS','wss://stream.bybit.com/v5/public/linear')
WORKER_URL=(os.environ.get('BYBIT_WORKER_URL') or 'https://trading-v77-scanner.hanlinh227.workers.dev').rstrip('/')
SECRET=(os.environ.get('BYBIT_VPS_BRIDGE_SECRET') or os.environ.get('V11_AI_BRIDGE_SECRET') or '').strip()
ENABLED=str(os.environ.get('BYBIT_EVENT_DRIVER_ENABLED','true')).lower() in ('1','true','yes')

class Driver:
    def __init__(self):
        self.lock=threading.RLock()
        self.bids={}; self.asks={}; self.trades=deque(maxlen=512)
        self.last_fingerprint=None; self.inflight=False; self.pending=False
        self.last_result=None; self.last_error=None; self.ws_connected=False

    @staticmethod
    def _imb(b,a):
        return (b-a)/(b+a) if b+a>0 else 0.0

    @staticmethod
    def _bucket(x,step):
        return int(round(float(x)/step)) if step>0 else int(round(float(x)))

    def _trade_imbalance(self,n):
        rows=list(self.trades)[-n:]
        buy=sell=0.0
        for side,q,p in rows:
            v=q*p
            if side=='Buy': buy+=v
            elif side=='Sell': sell+=v
        return self._imb(buy,sell)

    def _fingerprint(self,topic=''):
        with self.lock:
            if not self.bids or not self.asks:return None
            bids=sorted(self.bids.items(),reverse=True)[:50]; asks=sorted(self.asks.items())[:50]
            bb,bs=bids[0]; ba,as_=asks[0]; mid=(bb+ba)/2
            def depth(rows,bps):return sum(p*q for p,q in rows if abs(p-mid)/mid*10000<=bps)
            b2,a2=depth(bids,2),depth(asks,2); b5,a5=depth(bids,5),depth(asks,5)
            i2=self._imb(b2,a2); i5=self._imb(b5,a5)
            f64=self._trade_imbalance(64); f256=self._trade_imbalance(256)
            micro=(ba*bs+bb*as_)/(bs+as_) if bs+as_>0 else mid
            mp=(micro-mid)/mid*10000 if mid>0 else 0
            # Event-state buckets, not time buckets. Trigger only when market state meaningfully changes.
            return (
                self._bucket(mid,1.0),
                self._bucket(i2,.05),self._bucket(i5,.05),
                self._bucket(f64,.05),self._bucket(f256,.05),
                self._bucket(mp,.01),
                str(topic).split('.')[0]
            )

    def _wake_engine(self,reason):
        req=urllib.request.Request(
            WORKER_URL+'/bybit/auto/run',method='POST',data=b'{}',
            headers={'content-type':'application/json','accept':'application/json','x-action-key':SECRET,'x-btc-trigger':'VPS_WS_EVENT','x-btc-trigger-reason':reason[:120]}
        )
        try:
            with urllib.request.urlopen(req,timeout=30) as r:
                body=r.read(1_000_000).decode(errors='replace')
            try:self.last_result=json.loads(body)
            except Exception:self.last_result={'raw':body[:300]}
            self.last_error=None
        except Exception as e:
            self.last_error=str(e)[:300]
        finally:
            with self.lock:
                rerun=self.pending; self.pending=False
                if not rerun:self.inflight=False
            if rerun:
                self._spawn_wake('COALESCED_LATEST_STATE')

    def _spawn_wake(self,reason):
        if not ENABLED or not SECRET:return
        with self.lock:
            if self.inflight:
                self.pending=True; return
            self.inflight=True
        threading.Thread(target=self._wake_engine,args=(reason,),name='btc-engine-wake',daemon=True).start()

    def maybe_wake(self,topic):
        fp=self._fingerprint(topic)
        if fp is None:return
        with self.lock:
            if fp==self.last_fingerprint:return
            self.last_fingerprint=fp
        self._spawn_wake('MARKET_STATE_CHANGE:'+str(topic))

    def on_open(self,ws):
        self.ws_connected=True; self.last_error=None
        ws.send(json.dumps({'op':'subscribe','args':[f'orderbook.50.{SYMBOL}',f'publicTrade.{SYMBOL}',f'allLiquidation.{SYMBOL}']}))

    def on_close(self,_ws,_code,_msg):self.ws_connected=False
    def on_error(self,_ws,e):self.last_error='WS:'+str(e)[:260]

    def on_message(self,_ws,raw):
        try:msg=json.loads(raw)
        except Exception:return
        topic=str(msg.get('topic') or ''); data=msg.get('data') or {}
        changed=False
        with self.lock:
            if topic.startswith('orderbook.'):
                if msg.get('type')=='snapshot':
                    self.bids={float(p):float(q) for p,q in data.get('b',[]) if float(q)>0}; self.asks={float(p):float(q) for p,q in data.get('a',[]) if float(q)>0}
                else:
                    for p,q in data.get('b',[]):
                        p=float(p);q=float(q); self.bids.pop(p,None) if q==0 else self.bids.__setitem__(p,q)
                    for p,q in data.get('a',[]):
                        p=float(p);q=float(q); self.asks.pop(p,None) if q==0 else self.asks.__setitem__(p,q)
                changed=True
            elif topic==f'publicTrade.{SYMBOL}':
                for x in (data if isinstance(data,list) else [data]):
                    try:self.trades.append((str(x.get('S') or ''),float(x.get('v') or 0),float(x.get('p') or 0)));changed=True
                    except Exception:pass
            elif topic==f'allLiquidation.{SYMBOL}':
                changed=True
        if changed:self.maybe_wake(topic)

    def run(self):
        if websocket is None:raise SystemExit('websocket-client required')
        if not SECRET:raise SystemExit('BYBIT_VPS_BRIDGE_SECRET_OR_V11_AI_BRIDGE_SECRET_REQUIRED')
        if not ENABLED:raise SystemExit('BYBIT_EVENT_DRIVER_DISABLED')
        while True:
            app=websocket.WebSocketApp(WS_URL,on_open=self.on_open,on_message=self.on_message,on_error=self.on_error,on_close=self.on_close)
            app.run_forever(ping_interval=20,ping_timeout=10)

if __name__=='__main__':Driver().run()
