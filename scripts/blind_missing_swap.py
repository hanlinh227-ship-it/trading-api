#!/usr/bin/env python3
import json
from datetime import datetime, timezone
import blind_backtest_crypto as v6

COINS = ["POPCAT", "TAO", "TON", "FARTCOIN", "IP"]
CUTOFFS = v6.CUTOFFS


def load_swap(sym, cut):
    inst = f"{sym}-USDT-SWAP"
    frames, sums = {}, {}
    for k, bar in v6.TF.items():
        c = [x for x in v6.okx_hist(inst, bar, cut) if x["ts"] + v6.TF_MS[k] <= cut]
        if len(c) < 60:
            raise RuntimeError(f"{k} swap insufficient:{len(c)}")
        frames[k] = c
        sums[k] = v6.summ(c)
    return frames, sums


def evaluate_swap(sym, side, entry, sl, tp, cut):
    inst = f"{sym}-USDT-SWAP"
    end = cut + v6.MAX_FORWARD_HOURS * 3600000
    cursor = cut
    mfe = mae = 0.0
    seen = 0
    while cursor < end:
        nxt = min(end, cursor + 24 * 3600000)
        cs = [x for x in v6.okx_future_page(inst, cursor, nxt) if cursor <= x["ts"] < nxt]
        seen += len(cs)
        for x in cs:
            if side == "BUY":
                mfe=max(mfe,x["high"]-entry); mae=max(mae,entry-x["low"]); hs=x["low"]<=sl; ht=x["high"]>=tp
            else:
                mfe=max(mfe,entry-x["low"]); mae=max(mae,x["high"]-entry); hs=x["high"]>=sl; ht=x["low"]<=tp
            if hs and ht:return {"result":"AMBIGUOUS","mfe":mfe,"mae":mae,"candles":seen}
            if hs:return {"result":"SL","mfe":mfe,"mae":mae,"candles":seen}
            if ht:return {"result":"TP","mfe":mfe,"mae":mae,"candles":seen}
        cursor = nxt
    return {"result":"UNRESOLVED_72H","mfe":mfe,"mae":mae,"candles":seen}


def main():
    samples = {}
    for label, cutoff in CUTOFFS:
        cut = v6.iso_ms(cutoff)
        _, btc_frames, btc_sums = v6.load_frames("BTC", cut)
        results = []
        for sym in COINS:
            try:
                frames, sums = load_swap(sym, cut)
                side, sc, en, sl, tp, rr, model = v6.choose(sym, sums, frames, btc_frames, btc_sums)
                out = evaluate_swap(sym, side, en, sl, tp, cut)
                results.append({"symbol":sym+"USDT","cutoff":cutoff,"source":"OKX USDT-SWAP","blind":True,"decision":side,"score":round(sc,3),"entry":en,"sl":sl,"tp":tp,"plannedRR":round(rr,3),"model":model,"outcome":out})
            except Exception as e:
                results.append({"symbol":sym+"USDT","cutoff":cutoff,"error":str(e)})
        usable=[r for r in results if r.get("decision") in ("BUY","SELL")]
        resolved=[r for r in usable if r.get("outcome",{}).get("result") in ("TP","SL")]
        wins=[r for r in resolved if r["outcome"]["result"]=="TP"]
        losses=[r for r in resolved if r["outcome"]["result"]=="SL"]
        total_r=sum(r["plannedRR"] if r["outcome"]["result"]=="TP" else -1 for r in resolved)
        samples[label]={"summary":{"requested":len(COINS),"marketTrades":len(usable),"dataErrors":len(results)-len(usable),"resolved":len(resolved),"wins":len(wins),"losses":len(losses),"unresolved":len(usable)-len(resolved),"winRateResolved":round(100*len(wins)/len(resolved),2) if resolved else None,"expectancyR":round(total_r/len(resolved),3) if resolved else None},"tests":results}
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V6 missing Breakout coins via OKX USDT perpetual swap fallback","samples":samples}
    with open("data/blind_missing_swap.json","w",encoding="utf-8") as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v["summary"] for k,v in samples.items()},indent=2))

if __name__ == "__main__":
    main()
