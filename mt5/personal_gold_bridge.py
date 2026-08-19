import json, os, math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import MetaTrader5 as mt5

HOST=os.getenv("PGOLD_BRIDGE_HOST","127.0.0.1")
PORT=int(os.getenv("PGOLD_BRIDGE_PORT","8765"))
TOKEN=os.getenv("PGOLD_BRIDGE_TOKEN","")
SYMBOL=os.getenv("PGOLD_MT5_SYMBOL","XAUUSD")
MAGIC=int(os.getenv("PGOLD_MAGIC","771839"))
MAX_LOT=float(os.getenv("PGOLD_MAX_LOT","2.0"))


def ensure_mt5():
    if mt5.terminal_info() is not None:
        return True
    return bool(mt5.initialize())


def symbol_info():
    if not ensure_mt5():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    s=mt5.symbol_info(SYMBOL)
    if s is None:
        raise RuntimeError(f"Symbol not found: {SYMBOL}")
    if not s.visible and not mt5.symbol_select(SYMBOL,True):
        raise RuntimeError(f"Cannot select {SYMBOL}")
    return s


def lot_from_risk(side, entry, sl, risk_usd):
    s=symbol_info(); dist=abs(entry-sl)
    if dist<=0 or risk_usd<=0: raise ValueError("invalid risk/SL")
    tick_size=float(s.trade_tick_size or s.point or 0.01)
    tick_value=float(s.trade_tick_value_loss or s.trade_tick_value or 0)
    if tick_value<=0: raise RuntimeError("broker tick value unavailable")
    loss_per_lot=(dist/tick_size)*tick_value
    raw=risk_usd/loss_per_lot
    step=float(s.volume_step or 0.01); mn=float(s.volume_min or step); mx=min(float(s.volume_max or MAX_LOT),MAX_LOT)
    vol=max(mn,min(mx,math.floor(raw/step)*step))
    return round(vol,8)


def account_payload():
    if not ensure_mt5(): return {"ok":False,"error":str(mt5.last_error())}
    a=mt5.account_info(); t=mt5.terminal_info()
    if a is None: return {"ok":False,"error":"account_info unavailable"}
    return {"ok":True,"login":a.login,"balance":a.balance,"equity":a.equity,"marginFree":a.margin_free,"tradeAllowed":bool(t.trade_allowed if t else False),"symbol":SYMBOL}


def positions_payload():
    symbol_info(); ps=mt5.positions_get(symbol=SYMBOL) or []
    rows=[]
    for p in ps:
        rows.append({"ticket":p.ticket,"symbol":p.symbol,"type":p.type,"volume":p.volume,"priceOpen":p.price_open,"priceCurrent":p.price_current,"sl":p.sl,"tp":p.tp,"profit":p.profit})
    return {"ok":True,"count":len(rows),"positions":rows}


def place_order(body):
    s=symbol_info(); side=str(body.get("side","")).upper(); risk=float(body.get("riskUsd",0)); sl=float(body.get("sl",0)); tp=float(body.get("tp",0))
    tick=mt5.symbol_info_tick(SYMBOL)
    if tick is None: raise RuntimeError("tick unavailable")
    if side=="BUY": order_type=mt5.ORDER_TYPE_BUY; price=float(tick.ask)
    elif side=="SELL": order_type=mt5.ORDER_TYPE_SELL; price=float(tick.bid)
    else: raise ValueError("side must be BUY/SELL")
    volume=lot_from_risk(side,price,sl,risk)
    request={"action":mt5.TRADE_ACTION_DEAL,"symbol":SYMBOL,"volume":volume,"type":order_type,"price":price,"sl":sl,"tp":tp,"deviation":30,"magic":MAGIC,"comment":str(body.get("comment","PGOLD"))[:30],"type_time":mt5.ORDER_TIME_GTC,"type_filling":mt5.ORDER_FILLING_IOC}
    check=mt5.order_check(request)
    if check is None or check.retcode not in (0,):
        raise RuntimeError(f"order_check failed: {check}")
    result=mt5.order_send(request)
    if result is None: raise RuntimeError(f"order_send failed: {mt5.last_error()}")
    ok=result.retcode==mt5.TRADE_RETCODE_DONE
    return {"ok":ok,"retcode":result.retcode,"order":result.order,"deal":result.deal,"volume":result.volume,"price":result.price,"comment":result.comment,"request":request}


def close_position(body):
    ticket=int(body.get("positionId",0)); ps=mt5.positions_get(ticket=ticket) or []
    if not ps: raise ValueError("position not found")
    p=ps[0]; tick=mt5.symbol_info_tick(p.symbol)
    if tick is None: raise RuntimeError("tick unavailable")
    is_buy=p.type==mt5.POSITION_TYPE_BUY; typ=mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY; price=float(tick.bid if is_buy else tick.ask)
    req={"action":mt5.TRADE_ACTION_DEAL,"symbol":p.symbol,"volume":p.volume,"type":typ,"position":ticket,"price":price,"deviation":30,"magic":MAGIC,"comment":"PGOLD CLOSE","type_time":mt5.ORDER_TIME_GTC,"type_filling":mt5.ORDER_FILLING_IOC}
    res=mt5.order_send(req)
    if res is None: raise RuntimeError(str(mt5.last_error()))
    return {"ok":res.retcode==mt5.TRADE_RETCODE_DONE,"retcode":res.retcode,"order":res.order,"deal":res.deal,"price":res.price,"comment":res.comment}


class Handler(BaseHTTPRequestHandler):
    def _auth(self):
        return not TOKEN or self.headers.get("Authorization","")==f"Bearer {TOKEN}"
    def _json(self,status,payload):
        data=json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def _body(self):
        n=int(self.headers.get("Content-Length","0") or 0); return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        if not self._auth(): return self._json(401,{"ok":False,"error":"unauthorized"})
        try:
            if self.path=="/status": return self._json(200,account_payload())
            if self.path=="/positions": return self._json(200,positions_payload())
            return self._json(404,{"ok":False,"error":"not found"})
        except Exception as e: return self._json(500,{"ok":False,"error":str(e)})
    def do_POST(self):
        if not self._auth(): return self._json(401,{"ok":False,"error":"unauthorized"})
        try:
            body=self._body()
            if self.path=="/order": return self._json(200,place_order(body))
            if self.path=="/close": return self._json(200,close_position(body))
            return self._json(404,{"ok":False,"error":"not found"})
        except Exception as e: return self._json(500,{"ok":False,"error":str(e)})
    def log_message(self,fmt,*args): pass

if __name__=="__main__":
    print(f"PGOLD MT5 bridge http://{HOST}:{PORT} symbol={SYMBOL}")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
