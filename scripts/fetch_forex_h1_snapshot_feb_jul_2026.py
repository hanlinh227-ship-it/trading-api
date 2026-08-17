#!/usr/bin/env python3
import json, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAIRS=[
"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
"EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
"GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
"AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"]
START_DATE="2026-02-01 00:00:00"
END_DATE="2026-07-31 23:59:59"
INTERVAL="1h"
OUTPUTSIZE=5000
OUT="data/provider_snapshots/forex_h1_feb_jul_2026.json"


def parse_batch(payload):
    out={}
    if isinstance(payload,dict) and "values" in payload:
        meta=payload.get("meta") or {}
        sym=str(meta.get("symbol") or "").replace("/","").upper()
        if sym: out[sym]=payload
        return out
    if isinstance(payload,dict):
        for key,val in payload.items():
            if not isinstance(val,dict): continue
            q=val.get("data") if isinstance(val.get("data"),dict) else val
            if isinstance(q,dict) and isinstance(q.get("values"),list):
                meta=q.get("meta") or {}
                sym=str(meta.get("symbol") or key).replace("/","").upper()
                out[sym]=q
    return out


def request_json(url,timeout=120):
    req=urllib.request.Request(url,headers={"User-Agent":"trading-api-locked-snapshot/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read().decode("utf-8",errors="replace")
    return json.loads(raw)


def compact_values(values):
    out=[]
    for r in values:
        try:
            out.append([
                r["datetime"],
                float(r["open"]),float(r["high"]),float(r["low"]),float(r["close"])
            ])
        except Exception:
            continue
    out.sort(key=lambda x:x[0])
    return out


def main():
    key=os.environ.get("TWELVEDATA_API_KEY","").strip()
    if not key: raise RuntimeError("TWELVEDATA_API_KEY missing")
    all_data={}; diagnostics={}
    groups=[PAIRS[i:i+7] for i in range(0,len(PAIRS),7)]
    for idx,g in enumerate(groups):
        syms=",".join(f"{p[:3]}/{p[3:]}" for p in g)
        qs=urllib.parse.urlencode({
            "symbol":syms,
            "interval":INTERVAL,
            "outputsize":OUTPUTSIZE,
            "start_date":START_DATE,
            "end_date":END_DATE,
            "timezone":"UTC",
            "order":"asc",
            "apikey":key,
        })
        payload=request_json("https://api.twelvedata.com/time_series?"+qs)
        got=parse_batch(payload)
        missing=[p for p in g if p not in got]
        if missing:
            raise RuntimeError(f"batch {idx+1} missing {missing}: {str(payload)[:1200]}")
        for p in g:
            vals=compact_values(got[p].get("values") or [])
            if len(vals)<1500:
                raise RuntimeError(f"{p} too few H1 rows: {len(vals)}")
            first,last=vals[0][0],vals[-1][0]
            if first[:7] > "2026-02" or last[:10] < "2026-07-30":
                raise RuntimeError(f"{p} coverage invalid: {first} -> {last}")
            all_data[p]=vals
            diagnostics[p]={"bars":len(vals),"first":first,"last":last}
        print(f"SNAPSHOT_BATCH {idx+1}/4 OK: {','.join(g)}",flush=True)
        if idx < len(groups)-1:
            time.sleep(66)

    if set(all_data)!=set(PAIRS):
        raise RuntimeError("28-pair coverage check failed")
    doc={
        "version":"FOREX_H1_SNAPSHOT_FEB_JUL_2026_V1",
        "provider":"Twelve Data",
        "interval":"1h",
        "requestedPairs":PAIRS,
        "coverageCount":len(all_data),
        "startDate":START_DATE,
        "endDate":END_DATE,
        "fetchedAt":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "hiddenFinalHoldoutNotIncluded":"2026-08-01 onward",
        "diagnostics":diagnostics,
        "data":all_data,
    }
    Path(OUT).parent.mkdir(parents=True,exist_ok=True)
    with open(OUT,"w",encoding="utf-8") as f:
        json.dump(doc,f,separators=(",",":"))
    print(json.dumps({"status":"OK","path":OUT,"coverage":len(all_data),"totalBars":sum(x["bars"] for x in diagnostics.values()),"hiddenFinalHoldoutNotIncluded":True},indent=2),flush=True)

if __name__=="__main__":
    main()
