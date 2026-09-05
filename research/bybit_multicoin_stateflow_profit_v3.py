#!/usr/bin/env python3
"""Bybit MultiCoin StateFlow Profit-Aware V3 — research only.

V3 is a new, chronologically disjoint experiment after V2 showed that high
headline win rates can still have negative expectancy. V3 therefore selects
profiles on DEV using BOTH win-rate and positive after-cost expectancy, permits
one side to be disabled from DEV evidence, and uses wider profit targets with
less premature locking.

V3 OOS is older than both V1 and V2 evidence: 300d DEV + 3x50d OOS ending
at least 1100 days before the current dataset end. OOS is never used for
selection. If an exchange-history candle gap intersects the fixed block, the
whole block is shifted OLDER in deterministic 15-day steps based only on data
integrity, never on P/L or win rate.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
import bybit_multicoin_stateflow_dynamic_v2 as c

# Keep V3 evidence disjoint from V1 (~latest 450d) and V2 (~500-950d ago).
c.HISTORY_DAYS = 1800
c.SEEN_V1_BUFFER_DAYS = 1100
c.DEV_DAYS = 300
c.OOS_DAYS = 50
c.OOS_WINDOWS = 3
c.BASE_COST_BPS = 13.0
c.TARGET_WR = 0.80
c.WORST_FLOOR = 0.70
c.MIN_OOS = 60
c.MIN_WIN = 20

# stop ATR, target ATR, lock trigger ATR, trailing ATR, smart-cut ATR, max bars
# Compared with V2, winners must have enough room to pay for full losses + costs.
V3_MGMT = [
    (1.40, 0.85, 0.52, 0.42, 0.22, 20),
    (1.60, 1.00, 0.62, 0.48, 0.26, 24),
    (1.80, 1.15, 0.72, 0.54, 0.30, 28),
    (2.00, 1.30, 0.82, 0.60, 0.34, 32),
]

def candidates(side):
    for fam in ("TREND_RECLAIM", "BREAK_RETEST", "RANGE_FADE", "SWEEP_RECLAIM"):
        seps = (0.12, 0.24)
        qualities = (0.24, 0.38)
        vols = (0.90, 1.20)
        triggers = {
            "TREND_RECLAIM": (0.06, 0.18),
            "BREAK_RETEST": (0.00, 0.06),
            "RANGE_FADE": (0.85, 1.15),
            "SWEEP_RECLAIM": (0.03, 0.09),
        }[fam]
        mgmt_ids = (0, 1) if fam in ("RANGE_FADE", "SWEEP_RECLAIM") else (1, 2, 3)
        for sep in seps:
            for q in qualities:
                for v in vols:
                    for trig in triggers:
                        for mid in mgmt_ids:
                            st,tp,lock,trail,cut,hold = V3_MGMT[mid]
                            yield c.Profile(fam, side, sep, q, v, trig, st, tp, lock, trail, cut, hold)

def disabled(side):
    return c.Profile("DISABLED", side, 99.0, 99.0, 99.0, 99.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1)

def side_score(s):
    enough = s.trades >= 50
    econ = s.exp >= 0.02
    quality = s.wr >= 0.70
    return (1 if enough and econ and quality else 0, 1 if s.exp > 0 else 0, s.wr, s.exp, -s.max_dd_r, s.trades)

def combo_score(s):
    enough = s.trades >= 100
    econ = s.exp >= 0.04
    quality = s.wr >= 0.74
    return (1 if enough and econ and quality else 0, 1 if s.exp > 0 else 0, s.wr, s.exp, -s.max_dd_r, s.trades)

def choose_profiles(b, I, di):
    ranked = {}
    for side in (1, -1):
        arr=[]
        for p in candidates(side):
            s=c.run_side(b,I,p,di[0],di[1])
            arr.append((side_score(s),p,s))
        arr.sort(key=lambda z:z[0], reverse=True)
        ranked[side]=arr

    long_pool=[z[1] for z in ranked[1][:4]]+[disabled(1)]
    short_pool=[z[1] for z in ranked[-1][:4]]+[disabled(-1)]
    combos=[]
    for lp in long_pool:
        for sp in short_pool:
            if lp.family=="DISABLED" and sp.family=="DISABLED":
                continue
            ds=c.run_combo(b,I,lp,sp,di[0],di[1])
            combos.append((combo_score(ds),lp,sp,ds))
    combos.sort(key=lambda z:z[0], reverse=True)
    return combos[0], ranked

def select_clean_block(b):
    """Choose by DATA QUALITY only; never inspect trading outcome here."""
    for shift_days in range(0, 241, 15):
        anchor=b[-1].ts-(c.SEEN_V1_BUFFER_DAYS+shift_days)*c.DAY_MS
        oos_end=anchor
        oos_start=oos_end-c.OOS_WINDOWS*c.OOS_DAYS*c.DAY_MS+c.INTERVAL_MS
        dev_end=oos_start-c.INTERVAL_MS
        dev_start=dev_end-c.DEV_DAYS*c.DAY_MS+c.INTERVAL_MS
        di=c.idx(b,dev_start,dev_end)
        if not di or not c.clean(b,*di):
            continue
        windows=[]; ok=True
        for k in range(c.OOS_WINDOWS):
            st=oos_start+k*c.OOS_DAYS*c.DAY_MS
            en=st+c.OOS_DAYS*c.DAY_MS-c.INTERVAL_MS
            z=c.idx(b,st,en)
            if not z or not c.clean(b,*z):
                ok=False; break
            windows.append(z)
        if ok:
            return shift_days,di,windows
    return None

def calibrate(sym,b,manifest):
    I=c.prep(b)
    selected=select_clean_block(b)
    if not selected:
        return {"symbol":sym,"status":"DATA_GAP","reason":"No clean V3 block within deterministic 0-240d older shift","manifest":manifest}
    shift_days,di,windows=selected

    (_,lp,sp,dev_combo), ranked = choose_profiles(b,I,di)
    dev_long=c.run_side(b,I,lp,di[0],di[1]) if lp.family!="DISABLED" else c.Stats()
    dev_short=c.run_side(b,I,sp,di[0],di[1]) if sp.family!="DISABLED" else c.Stats()

    ws=[c.run_combo(b,I,lp,sp,lo,hi) for lo,hi in windows]
    agg=c.merge(ws)
    worst=min((x.wr for x in ws),default=0.0)
    base=(agg.wr>=c.TARGET_WR and worst>=c.WORST_FLOOR and agg.trades>=c.MIN_OOS
          and all(x.trades>=c.MIN_WIN for x in ws) and agg.exp>0 and all(x.net_r>0 for x in ws))
    st15=c.merge([c.run_combo(b,I,lp,sp,lo,hi,cost_bps=c.BASE_COST_BPS*1.5) for lo,hi in windows])
    st20=c.merge([c.run_combo(b,I,lp,sp,lo,hi,cost_bps=c.BASE_COST_BPS*2.0) for lo,hi in windows])
    delay=c.merge([c.run_combo(b,I,lp,sp,lo,hi,delay=1) for lo,hi in windows])
    robust=st15.exp>0 and st20.exp>0 and delay.exp>0
    status="LOCKED" if base and robust else "RESEARCH"
    reason=[]
    if status!="LOCKED":
        if agg.wr<c.TARGET_WR:reason.append("OOS_WR_LT_80")
        if worst<c.WORST_FLOOR:reason.append("WORST_WINDOW_LT_70")
        if agg.trades<c.MIN_OOS:reason.append("OOS_TRADES_LT_60")
        if any(x.trades<c.MIN_WIN for x in ws):reason.append("WINDOW_TRADES_LT_20")
        if agg.exp<=0:reason.append("NONPOSITIVE_EXPECTANCY")
        if any(x.net_r<=0 for x in ws):reason.append("NEGATIVE_WINDOW_R")
        if not robust:reason.append("STRESS_FAIL")

    return {
        "symbol":sym,"status":status,"reason":"PASS" if status=="LOCKED" else reason,
        "profile_version":"stateflow_profit_v3_gap_safe","long_profile_hash":c.ph(lp),"short_profile_hash":c.ph(sp),
        "long_params":c.pd(lp),"short_params":c.pd(sp),"manifest":manifest,
        "validation_block_policy":{"base_end_buffer_days":c.SEEN_V1_BUFFER_DAYS,"data_gap_shift_older_days":shift_days,"shift_rule":"first clean block in 15d increments; data quality only","dev_days":c.DEV_DAYS,"oos_windows":c.OOS_WINDOWS,"oos_days":c.OOS_DAYS,"disjoint_from":"V1,V2"},
        "dev_range":[c.iso(b[di[0]].ts),c.iso(b[di[1]].ts)],"dev_combined":c.statd(dev_combo),"dev_long":c.statd(dev_long),"dev_short":c.statd(dev_short),
        "oos_windows":[{"range":[c.iso(b[lo].ts),c.iso(b[hi].ts)],**c.statd(s)} for (lo,hi),s in zip(windows,ws)],
        "oos_aggregate":c.statd(agg),"worst_window_wr":round(worst,6),
        "stress":{"cost_1_5x":c.statd(st15),"cost_2_0x":c.statd(st20),"entry_delay_1bar":c.statd(delay),"pass":robust},
        "gate":{"target_wr":c.TARGET_WR,"worst_window_floor":c.WORST_FLOOR,"min_oos_trades":c.MIN_OOS,"min_window_trades":c.MIN_WIN,"base_pass":base,"locked":status=="LOCKED"},
        "limitations":["OHLCV state proxy only","V3 DEV/OOS disjoint from V1/V2","No L2/taker-flow/liquidation/OI replay","Microstructure replay/forward-paper required before production"]
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--symbols",default=",".join(c.UNIVERSE));ap.add_argument("--out",default="research/results/bybit_multicoin_stateflow_profit_v3.json");a=ap.parse_args()
    syms=[x.strip().upper() for x in a.symbols.split(",") if x.strip()];res=[]
    print("=== BYBIT MULTICOIN STATEFLOW PROFIT-AWARE V3 GAP-SAFE ===",flush=True)
    for n,sym in enumerate(syms,1):
        print(f"[{n}/{len(syms)}] {sym} load",flush=True)
        try:
            b,m=c.load(sym);print(f"DATA {sym} bars={m['bars']} coverage={m['coverage']:.6f} gaps={m['gaps']}",flush=True);r=calibrate(sym,b,m)
        except Exception as e:r={"symbol":sym,"status":"ERROR","reason":repr(e)}
        res.append(r)
        if r.get("oos_aggregate"):
            x=r["oos_aggregate"];shift=r['validation_block_policy']['data_gap_shift_older_days'];print(f"RESULT {sym} {r['status']} WR={100*x['win_rate']:.2f}% N={x['trades']} ExpR={x['expectancy_r']:+.4f} worst={100*r['worst_window_wr']:.2f}% LONG={r['long_params']['family']} SHORT={r['short_params']['family']} DEV_WR={100*r['dev_combined']['win_rate']:.2f}% DEV_ExpR={r['dev_combined']['expectancy_r']:+.4f} SHIFT={shift}d reason={r['reason']}",flush=True)
        else:print("RESULT",sym,r["status"],r.get("reason"),flush=True)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    summary={"generated_at":datetime.now(timezone.utc).isoformat(),"engine":"BYBIT_MULTICOIN_STATEFLOW_PROFIT_V3_GAP_SAFE","research_only":True,"universe":syms,"locked":[r["symbol"] for r in res if r.get("status")=="LOCKED"],"unresolved":[r["symbol"] for r in res if r.get("status")!="LOCKED"],"results":res}
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LOCKED",summary["locked"],flush=True);print("REPORT",out,flush=True)
if __name__=="__main__":main()
