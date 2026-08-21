import json
import math
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
LOGS = ROOT / "logs"
STATE = ROOT / "state"
TRADES = LOGS / "paper_trades.jsonl"
OUTPUT = STATE / "learning_stats.json"
CANDIDATE_POLICY = STATE / "research_policy_candidate.json"

MIN_EVALUABLE = 30
MIN_STRONG = 100


def bucket():
    return {"closed":0,"wins":0,"losses":0,"gross_profit":0.0,"gross_loss":0.0,"net_pnl":0.0}


def update(s, pnl):
    s["closed"] += 1
    s["net_pnl"] += pnl
    if pnl > 0:
        s["wins"] += 1; s["gross_profit"] += pnl
    elif pnl < 0:
        s["losses"] += 1; s["gross_loss"] += abs(pnl)


def summarize(s):
    n = s["closed"]
    wr = s["wins"] / n * 100.0 if n else 0.0
    pf = s["gross_profit"] / s["gross_loss"] if s["gross_loss"] else (999.0 if s["gross_profit"] else 0.0)
    avg = s["net_pnl"] / n if n else 0.0
    return {**s,"win_rate":round(wr,2),"avg_pnl":round(avg,6),"profit_factor":round(pf,3),"sample_status":"RESEARCH_ONLY" if n < MIN_EVALUABLE else "EVALUATABLE" if n < MIN_STRONG else "STRONG_SAMPLE"}


def bounded_multiplier(summary):
    n = int(summary.get("closed", 0))
    if n < MIN_EVALUABLE:
        return 1.0
    pf = min(3.0, float(summary.get("profit_factor", 0.0)))
    wr = float(summary.get("win_rate", 0.0)) / 100.0
    avg = float(summary.get("avg_pnl", 0.0))
    evidence = 0.55 * math.tanh(pf - 1.0) + 0.35 * math.tanh((wr - 0.5) * 3.0) + 0.10 * math.tanh(avg)
    sample_weight = min(1.0, (n - MIN_EVALUABLE + 1) / 120.0)
    return round(max(0.90, min(1.10, 1.0 + evidence * sample_weight * 0.10)), 4)


def main():
    pair_stats = defaultdict(bucket); strategy_stats = defaultdict(bucket); symbol_stats = defaultdict(bucket); regime_stats = defaultdict(bucket)
    if TRADES.exists():
        for line in TRADES.read_text(encoding="utf-8", errors="replace").splitlines():
            try: e = json.loads(line)
            except Exception: continue
            if e.get("event") != "PAPER_CLOSE": continue
            symbol = str(e.get("symbol", "UNKNOWN")).upper(); strategy = str(e.get("strategy", "UNKNOWN")).upper(); regime = str(e.get("regime", "UNKNOWN")).upper()
            pnl = float(e.get("total_pnl", e.get("pnl", 0)) or 0)
            update(pair_stats[f"{symbol}::{strategy}"], pnl); update(strategy_stats[strategy], pnl); update(symbol_stats[symbol], pnl); update(regime_stats[regime], pnl)
    pair_out = {k:summarize(v) for k,v in pair_stats.items()}; strategy_out = {k:summarize(v) for k,v in strategy_stats.items()}; symbol_out = {k:summarize(v) for k,v in symbol_stats.items()}; regime_out = {k:summarize(v) for k,v in regime_stats.items()}
    generated = datetime.now(timezone.utc).isoformat()
    payload = {"generated_at":generated,"principle":"Research journal is advisory. Runtime policy is owned by learning/continuous_learner.py.","minimum_evaluable_closed_trades":MIN_EVALUABLE,"strong_sample_closed_trades":MIN_STRONG,"symbol_strategy":pair_out,"strategy":strategy_out,"symbol":symbol_out,"regime":regime_out}
    STATE.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    candidate = {"generated_at":generated,"status":"RESEARCH_CANDIDATE_ONLY","range":[0.90,1.10],"strategy_multipliers":{k:bounded_multiplier(v) for k,v in strategy_out.items()},"symbol_multipliers":{k:bounded_multiplier(v) for k,v in symbol_out.items()},"regime_multipliers":{k:bounded_multiplier(v) for k,v in regime_out.items()},"live_auto_promotion":False}
    CANDIDATE_POLICY.write_text(json.dumps(candidate, indent=2, ensure_ascii=False), encoding="utf-8")
    print("LEARNING JOURNAL:", len(pair_out), "symbol/strategy buckets | advisory only")
    for k,v in sorted(pair_out.items(), key=lambda kv: kv[1]["closed"], reverse=True)[:10]: print(k, "| n", v["closed"], "| WR", v["win_rate"], "| PF", v["profit_factor"], "| PnL", round(v["net_pnl"],4), "|", v["sample_status"])


if __name__ == "__main__":
    main()
