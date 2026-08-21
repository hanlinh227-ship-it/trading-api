import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
LOGS = ROOT / "logs"
POSITIONS_FILE = STATE / "paper_positions.json"
RISK_FILE = STATE / "risk_decisions.json"
TRADES_LOG = LOGS / "paper_trades.jsonl"
BASE = "https://fapi.binance.com"
DEFAULT_STARTING_EQUITY = 50.0


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_price(symbol):
    with urllib.request.urlopen(f"{BASE}/fapi/v1/ticker/price?symbol={symbol}", timeout=10) as r:
        return float(json.loads(r.read().decode())["price"])


def pnl(side, entry, exit_price, qty):
    return (exit_price-entry)*qty if side == "LONG" else (entry-exit_price)*qty


def log_event(event):
    LOGS.mkdir(parents=True, exist_ok=True)
    with TRADES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False)+"\n")


def size_for_risk(equity, entry, stop, risk_pct, leverage):
    distance = abs(entry-stop)
    if equity <= 0 or distance <= 0:
        return 0.0
    risk_usd = equity * risk_pct / 100.0
    qty_risk = risk_usd / distance
    qty_margin = equity * leverage / entry
    return max(0.0, min(qty_risk, qty_margin))


def close_partial(p, price, fraction, event):
    qty = min(p["quantity"]*fraction, p["remaining_qty"])
    if qty <= 0:
        return
    gain = pnl(p["side"], p["entry"], price, qty)
    p["remaining_qty"] -= qty
    p["realized_pnl"] += gain
    log_event({"event":event,"timestamp":now(),"symbol":p["symbol"],"strategy":p.get("strategy"),"price":price,"quantity":qty,"pnl":gain,"remaining_qty":p["remaining_qty"]})


def close_all(p, price, reason):
    qty = p["remaining_qty"]
    gain = pnl(p["side"], p["entry"], price, qty) if qty > 0 else 0.0
    p["remaining_qty"] = 0.0; p["realized_pnl"] += gain; p["status"] = "CLOSED"; p["closed_at"] = now(); p["close_reason"] = reason
    log_event({"event":"PAPER_CLOSE","timestamp":now(),"symbol":p["symbol"],"strategy":p.get("strategy"),"price":price,"reason":reason,"pnl":gain,"total_pnl":p["realized_pnl"]})


def manage_position(p, price):
    long = p["side"] == "LONG"
    if (long and price <= p["stop_loss"]) or ((not long) and price >= p["stop_loss"]):
        close_all(p, price, "STOP"); return
    hit1 = p.get("tp1") is not None and ((long and price >= p["tp1"]) or ((not long) and price <= p["tp1"]))
    if hit1 and not p.get("tp1_done"):
        close_partial(p, price, p["tp1_fraction"], "TP1"); p["tp1_done"] = True
        if p.get("breakeven_after_tp1", True):
            p["stop_loss"] = p["entry"]; p["break_even"] = True
    hit2 = p.get("tp2") is not None and ((long and price >= p["tp2"]) or ((not long) and price <= p["tp2"]))
    if hit2 and not p.get("tp2_done"):
        close_partial(p, price, p["tp2_fraction"], "TP2"); p["tp2_done"] = True; p["trailing_active"] = True
    if p.get("trailing_active"):
        distance = p["initial_risk"] * p.get("trail_factor", 0.85)
        candidate = price-distance if long else price+distance
        if long:
            p["stop_loss"] = max(p["stop_loss"], candidate)
        else:
            p["stop_loss"] = min(p["stop_loss"], candidate)
    hit3 = p.get("tp3") is not None and ((long and price >= p["tp3"]) or ((not long) and price <= p["tp3"]))
    if hit3:
        close_all(p, price, "TP3")


def main():
    risk = load(RISK_FILE, {"decisions":{}})
    state = load(POSITIONS_FILE, {"mode":"PAPER","starting_equity":DEFAULT_STARTING_EQUITY,"equity":DEFAULT_STARTING_EQUITY,"positions":[]})
    positions = state.setdefault("positions", [])
    starting = float(state.get("starting_equity", DEFAULT_STARTING_EQUITY))
    realized = sum(float(p.get("realized_pnl",0) or 0) for p in positions)
    equity = starting + realized
    open_symbols = {p.get("symbol") for p in positions if p.get("status")=="OPEN"}

    for symbol, d in risk.get("decisions", {}).items():
        if not d.get("approved") or d.get("action") not in {"LONG","SHORT"} or symbol in open_symbols:
            continue
        entry, stop = d.get("entry"), d.get("stop_loss")
        if entry is None or stop is None:
            continue
        entry, stop = float(entry), float(stop)
        qty = size_for_risk(equity, entry, stop, float(d.get("risk_pct",0.5)), int(d.get("max_leverage",3)))
        if qty <= 0:
            continue
        m = d.get("management") or {}
        p = {"id":f"{symbol}-{int(datetime.now().timestamp())}","symbol":symbol,"strategy":d.get("strategy","NO_EDGE"),"side":d["action"],"entry":entry,"stop_loss":stop,"initial_stop":stop,"initial_risk":abs(entry-stop),"tp1":d.get("tp1"),"tp2":d.get("tp2"),"tp3":d.get("tp3"),"quantity":qty,"remaining_qty":qty,"tp1_fraction":float(m.get("tp1_close_pct",30))/100.0,"tp2_fraction":float(m.get("tp2_close_pct",30))/100.0,"trail_factor":float(m.get("trail_atr_mult",0.85)),"breakeven_after_tp1":bool(m.get("breakeven_after_tp1",True)),"tp1_done":False,"tp2_done":False,"break_even":False,"trailing_active":False,"realized_pnl":0.0,"status":"OPEN","opened_at":now(),"closed_at":None}
        positions.append(p); open_symbols.add(symbol); log_event({"event":"PAPER_OPEN","timestamp":now(),**p})

    for p in positions:
        if p.get("status") != "OPEN":
            continue
        try:
            manage_position(p, get_price(p["symbol"]))
        except Exception as exc:
            log_event({"event":"PRICE_ERROR","timestamp":now(),"symbol":p.get("symbol"),"error":repr(exc)})

    realized = sum(float(p.get("realized_pnl",0) or 0) for p in positions)
    state.update({"mode":"PAPER","updated_at":now(),"starting_equity":starting,"equity":starting+realized,"realized_pnl":realized,"positions":positions,"daily_trade_limit":None,"daily_loss_limit":None})
    save(POSITIONS_FILE, state)
    open_pos = [p for p in positions if p.get("status")=="OPEN"]
    print("="*48); print("V4 PAPER SCALP POSITION MANAGER"); print("="*48)
    print("EQUITY:", round(state["equity"],4), "| OPEN:", len(open_pos), "| CLOSED:", len(positions)-len(open_pos), "| REALIZED:", round(realized,4))
    for p in open_pos:
        print(p["symbol"], p["strategy"], p["side"], "| entry", p["entry"], "| SL", round(p["stop_loss"],8), "| qty", round(p["remaining_qty"],8))
    print("PAPER MODE ONLY - NO REAL BINANCE ORDER WAS SENT")


if __name__ == "__main__":
    main()
