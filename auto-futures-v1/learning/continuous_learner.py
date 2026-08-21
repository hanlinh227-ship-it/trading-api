import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
LOGS = ROOT / "logs"
POSITIONS = STATE / "paper_positions.json"
POLICY = STATE / "adaptive_policy.json"
REPORT = STATE / "learning_report.json"

MIN_TRADES_STRATEGY = 30
MIN_TRADES_SYMBOL = 40
MIN_TRADES_REGIME = 30
MAX_MULTIPLIER_MOVE = 0.15


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def summarize(rows):
    n = len(rows)
    wins = [x for x in rows if x > 0]
    losses = [x for x in rows if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    net = sum(rows)
    avg = net / n if n else 0.0
    win_rate = len(wins) / n if n else 0.0
    pf = gross_profit / gross_loss if gross_loss > 0 else (9.99 if gross_profit > 0 else 0.0)
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 4),
        "net_pnl": round(net, 8),
        "avg_pnl": round(avg, 8),
        "profit_factor": round(pf, 4),
    }


def learned_multiplier(stats, minimum):
    n = stats["trades"]
    if n < minimum:
        return 1.0, "RESEARCH_ONLY"
    pf = stats["profit_factor"]
    wr = stats["win_rate"]
    edge = 0.0
    edge += clamp((pf - 1.0) / 1.5, -1.0, 1.0) * 0.55
    edge += clamp((wr - 0.50) / 0.20, -1.0, 1.0) * 0.30
    edge += (0.15 if stats["avg_pnl"] > 0 else -0.15 if stats["avg_pnl"] < 0 else 0.0)
    confidence = clamp((n - minimum) / max(minimum * 3.0, 1.0), 0.0, 1.0)
    move = clamp(edge * confidence * MAX_MULTIPLIER_MOVE, -MAX_MULTIPLIER_MOVE, MAX_MULTIPLIER_MOVE)
    return round(1.0 + move, 4), "ACTIVE_LEARNED"


def main():
    state = load(POSITIONS, {"positions": []})
    closed = [p for p in state.get("positions", []) if p.get("status") == "CLOSED"]

    by_strategy = defaultdict(list)
    by_symbol = defaultdict(list)
    by_regime = defaultdict(list)
    by_combo = defaultdict(list)

    for p in closed:
        pnl = float(p.get("realized_pnl", 0) or 0)
        strategy = str(p.get("strategy", "UNKNOWN"))
        symbol = str(p.get("symbol", "UNKNOWN"))
        regime = str(p.get("regime", "UNKNOWN"))
        by_strategy[strategy].append(pnl)
        by_symbol[symbol].append(pnl)
        by_regime[regime].append(pnl)
        by_combo[f"{symbol}|{strategy}|{regime}"].append(pnl)

    strategy_stats = {k: summarize(v) for k, v in by_strategy.items()}
    symbol_stats = {k: summarize(v) for k, v in by_symbol.items()}
    regime_stats = {k: summarize(v) for k, v in by_regime.items()}
    combo_stats = {k: summarize(v) for k, v in by_combo.items()}

    strategy_mult = {}
    strategy_status = {}
    for k, s in strategy_stats.items():
        m, status = learned_multiplier(s, MIN_TRADES_STRATEGY)
        strategy_mult[k] = m
        strategy_status[k] = status

    symbol_mult = {}
    symbol_status = {}
    for k, s in symbol_stats.items():
        m, status = learned_multiplier(s, MIN_TRADES_SYMBOL)
        symbol_mult[k] = m
        symbol_status[k] = status

    regime_mult = {}
    regime_status = {}
    for k, s in regime_stats.items():
        m, status = learned_multiplier(s, MIN_TRADES_REGIME)
        regime_mult[k] = m
        regime_status[k] = status

    policy = {
        "generated_at": now(),
        "status": "ACTIVE" if closed else "DEFAULT_NO_CLOSED_TRADES",
        "closed_trades": len(closed),
        "method": "shrunk champion-policy; no source-code self-modification",
        "strategy_multipliers": strategy_mult,
        "symbol_multipliers": symbol_mult,
        "regime_multipliers": regime_mult,
        "guardrails": {
            "minimum_strategy_trades": MIN_TRADES_STRATEGY,
            "minimum_symbol_trades": MIN_TRADES_SYMBOL,
            "minimum_regime_trades": MIN_TRADES_REGIME,
            "max_score_multiplier_move": MAX_MULTIPLIER_MOVE,
            "source_code_auto_rewrite": False,
            "paper_evidence_required": True,
        },
    }

    report = {
        "generated_at": policy["generated_at"],
        "closed_trades": len(closed),
        "strategy_stats": strategy_stats,
        "symbol_stats": symbol_stats,
        "regime_stats": regime_stats,
        "combo_stats": combo_stats,
        "strategy_status": strategy_status,
        "symbol_status": symbol_status,
        "regime_status": regime_status,
        "policy": policy,
    }

    STATE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    POLICY.write_text(json.dumps(policy, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (LOGS / "learning.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"generated_at": policy["generated_at"], "closed_trades": len(closed), "strategy_multipliers": strategy_mult, "regime_multipliers": regime_mult}) + "\n")

    print("=" * 72)
    print("CONTINUOUS LEARNING POLICY")
    print("=" * 72)
    print("Closed trades:", len(closed), "| status:", policy["status"])
    for k, s in sorted(strategy_stats.items()):
        print("STRATEGY", k, "| N", s["trades"], "| WR", s["win_rate"], "| PF", s["profit_factor"], "| MULT", strategy_mult.get(k, 1.0), "|", strategy_status.get(k))
    print("No live source-code self-rewrite. Learned weights are evidence-gated and bounded.")


if __name__ == "__main__":
    main()
