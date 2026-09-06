#!/usr/bin/env python3
"""Scalp Fixed-RR V5.

V5 keeps the V4 optimizer/gates unchanged but replaces direct Bybit REST
historical loading (blocked with HTTP 403 on US GitHub-hosted runners) with
Binance USD-M Futures Data Vision monthly 5m archives as the historical
futures research proxy. Production target remains Bybit; therefore any LOCKED
historical profile still requires Bybit microstructure replay/forward-paper.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import bybit_multicoin_scalp_rr_v4 as v

ARCHIVE = "https://data.binance.vision/data/futures/um/monthly/klines"
MONTHS = 23  # enough for V4's 620-day split with warmup and complete months


def month_keys(end_year: int, end_month: int, count: int):
    out=[]
    y,m=end_year,end_month
    for _ in range(count):
        out.append((y,m))
        m-=1
        if m==0:
            y-=1;m=12
    return list(reversed(out))


def norm_ts(x: int) -> int:
    # Defensive support if an archive ever stores microseconds instead of ms.
    return x // 1000 if x > 10**15 else x


def fetch_zip(url: str, retries: int = 5):
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"scalp-rr-v5/1.0"})
            with urllib.request.urlopen(req,timeout=45) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code==404:
                return None
            last=e
        except Exception as e:
            last=e
        time.sleep(min(4.0,0.35*(2**n)))
    raise RuntimeError(last)


def load_futures_archive(sym: str):
    now=datetime.now(timezone.utc)
    # Use the most recent fully completed calendar month only.
    y,m=now.year,now.month-1
    if m==0:
        y-=1;m=12
    rows={};downloads=0;missing=[]
    for yy,mm in month_keys(y,m,MONTHS):
        ym=f"{yy:04d}-{mm:02d}"
        url=f"{ARCHIVE}/{sym}/5m/{sym}-5m-{ym}.zip"
        raw=fetch_zip(url)
        if raw is None:
            missing.append(ym)
            continue
        downloads+=1
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names=[n for n in zf.namelist() if n.lower().endswith('.csv')]
            if not names:
                raise RuntimeError(f"no csv in {url}")
            text=zf.read(names[0]).decode('utf-8-sig')
        for r in csv.reader(io.StringIO(text)):
            if not r or not r[0].strip().isdigit():
                continue
            ts=norm_ts(int(r[0]))
            try:
                rows[ts]=v.Bar(ts,float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[5]))
            except (ValueError,IndexError):
                continue
    b=[rows[k] for k in sorted(rows)]
    if len(b)<100_000:
        raise RuntimeError(f"insufficient USD-M futures 5m history bars={len(b)} missing_months={missing}")
    gaps=[(a.ts,z.ts) for a,z in zip(b,b[1:]) if z.ts-a.ts!=v.INTERVAL_MS]
    expected=(b[-1].ts-b[0].ts)//v.INTERVAL_MS+1
    manifest={
        "source":"BinanceDataVisionUSD-MFuturesProxyForBybit",
        "contract":"USD-M perpetual futures research proxy",
        "target_execution_venue":"Bybit Linear",
        "symbol":sym,"interval":"5m",
        "first":v.iso(b[0].ts),"last":v.iso(b[-1].ts),
        "bars":len(b),"expected":expected,"coverage":len(b)/expected,
        "gaps":len(gaps),"gap_examples":[(v.iso(a),v.iso(z)) for a,z in gaps[:10]],
        "archive_months_downloaded":downloads,"missing_months":missing,
    }
    return b,manifest


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--symbols',default=','.join(v.UNIVERSE))
    ap.add_argument('--out',default='research/results/bybit_multicoin_scalp_rr_v5.json')
    a=ap.parse_args();syms=[x.strip().upper() for x in a.symbols.split(',') if x.strip()]
    res=[]
    print('=== MULTICOIN SCALP FIXED-RR V5 / USD-M FUTURES ARCHIVE ===',flush=True)
    for n,sym in enumerate(syms,1):
        print(f'[{n}/{len(syms)}] {sym} load futures 5m archive',flush=True)
        try:
            b,m=load_futures_archive(sym)
            print(f"DATA {sym} bars={m['bars']} coverage={m['coverage']:.6f} gaps={m['gaps']} months={m['archive_months_downloaded']}",flush=True)
            r=v.calibrate(sym,b,m)
            if r.get('limitations'):
                r['limitations'].append('Historical venue is Binance USD-M futures proxy; Bybit forward/replay required')
            r['profile_version']='scalp_rr_v5_futures_proxy'
        except Exception as e:
            r={'symbol':sym,'status':'ERROR','reason':repr(e)}
        res.append(r)
        if r.get('final_aggregate'):
            x=r['final_aggregate']
            print(f"RESULT {sym} {r['status']} FINAL_WR={100*x['win_rate']:.2f}% N={x['trades']} ExpR={x['expectancy_r']:+.4f} worst={100*r['worst_final_window_wr']:.2f}% LONG={r['long_profile']['family']}/RR{r['long_profile']['rr']} SHORT={r['short_profile']['family']}/RR{r['short_profile']['rr']} DEV_WR={100*r['dev']['win_rate']:.2f}% SHADOW_WR={100*r['shadow']['win_rate']:.2f}% reason={r['reason']}",flush=True)
        else:
            print('RESULT',sym,r['status'],r.get('reason'),flush=True)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    summary={'generated_at':datetime.now(timezone.utc).isoformat(),'engine':'MULTICOIN_SCALP_RR_V5_FUTURES_PROXY',
             'research_only':True,'universe':syms,
             'locked':[r['symbol'] for r in res if r.get('status')=='LOCKED'],
             'unresolved':[r['symbol'] for r in res if r.get('status')!='LOCKED'],'results':res}
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LOCKED',summary['locked'],flush=True);print('REPORT',out,flush=True)

if __name__=='__main__':
    main()
