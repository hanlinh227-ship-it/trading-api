import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
LOGS = ROOT / "logs"
STATE = ROOT / "state"
TRADES = LOGS / "paper_trades.jsonl"
OUTPUT = STATE / "learning_stats.json"


def main():
    stats = defaultdict(lambda: {"closed":0,"wins":0,"losses":0,"gross_profit":0.0,"gross_loss":0.0,"net_pnl":0.0})
    if TRADES.exists():
        for line in TRADES.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("event") != "PAPER_CLOSE":
                continue
            key = f"{e.get('symbol','UNKNOWN')}::{e.get('strategy','UNKNOWN')}"
            pnl = float(e.get("total_pnl", e.get("pnl", 0)) or 0)
            s = stats[key]; s["closed"] += 1; s["net_pnl"] += pnl
            if pnl > 0:
                s["wins"] += 1; s["gross_profit"] += pnl
            elif pnl < 0:
                s["losses"] += 1; s["gross_loss"] += abs(pnl)
    out = {}
    for key, s in stats.items():
        n = s["closed"]
        out[key] = {**s,"win_rate":round(s["wins"]/n*100,2) if n else 0.0,"avg_pnl":round(s["net_pnl"]/n,6) if n else 0.0,"profit_factor":round(s["gross_profit"]/s["gross_loss"],3) if s["gross_loss"] else (999.0 if s["gross_profit"] else 0.0),"sample_status":"RESEARCH_ONLY" if n < 30 else "EVALUATABLE"}
    payload = {"generated_at":datetime.now(timezone.utc).isoformat(),"principle":"Observed performance informs research; it never self-promotes a live strategy without validation.","minimum_evaluable_closed_trades":30,"stats":out}
    STATE.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("LEARNING JOURNAL:", len(out), "symbol/strategy buckets")
    for k,v in sorted(out.items(), key=lambda kv: kv[1]["closed"], reverse=True)[:10]:
        print(k, "| n", v["closed"], "| WR", v["win_rate"], "| PF", v["profit_factor"], "| PnL", round(v["net_pnl"],4), "|", v["sample_status"])


if __name__ == "__main__":
    main()
