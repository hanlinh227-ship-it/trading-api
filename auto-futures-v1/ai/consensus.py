import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
AI_DIR = ROOT / "ai"
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"
SCRIPTS = {"claude":"claude_trader.py","deepseek":"deepseek_trader.py","codex":"codex_trader.py"}


def run_ai(name, script):
    try:
        p = subprocess.run(["python3", script], cwd=AI_DIR, capture_output=True, text=True, timeout=220)
        if p.returncode != 0:
            return name, {"status":"ERROR","error":p.stderr[-1500:],"reviews":{}}
        out = p.stdout.strip()
        if not out:
            return name, {"status":"ERROR","error":"EMPTY_OUTPUT","reviews":{}}
        return name, json.loads(out.splitlines()[-1])
    except Exception as exc:
        return name, {"status":"ERROR","error":repr(exc),"reviews":{}}


def main():
    print("Starting Claude + DeepSeek + Codex scalp reviewers in parallel...", flush=True)
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_ai, n, s) for n, s in SCRIPTS.items()]
        for f in futures:
            n, r = f.result(); results[n] = r

    review_maps = {n: (results.get(n, {}).get("reviews", {}) or {}) for n in SCRIPTS}
    symbols = sorted(set().union(*(set(x) for x in review_maps.values())))
    decisions = {}

    for symbol in symbols:
        reviews = {n: review_maps[n].get(symbol) for n in SCRIPTS}
        available = {n:r for n,r in reviews.items() if isinstance(r, dict)}
        actions = [str(r.get("action", "WAIT")).upper() for r in available.values()]
        confidences = [float(r.get("confidence", 0) or 0) for r in available.values()]
        longs, shorts, waits = actions.count("LONG"), actions.count("SHORT"), actions.count("WAIT")
        final_action, reason = "WAIT", "NO_EDGE"

        if len(available) < 3:
            reason = "MISSING_AI_REVIEW"
        elif longs >= 2 and shorts == 0:
            directional = [float(r.get("confidence",0) or 0) for r in available.values() if str(r.get("action","")).upper()=="LONG"]
            if directional and sum(directional)/len(directional) >= 62:
                final_action, reason = "LONG", "TWO_OF_THREE_PLUS_NO_OPPOSITION"
            else:
                reason = "LONG_CONFIDENCE_TOO_LOW"
        elif shorts >= 2 and longs == 0:
            directional = [float(r.get("confidence",0) or 0) for r in available.values() if str(r.get("action","")).upper()=="SHORT"]
            if directional and sum(directional)/len(directional) >= 62:
                final_action, reason = "SHORT", "TWO_OF_THREE_PLUS_NO_OPPOSITION"
            else:
                reason = "SHORT_CONFIDENCE_TOO_LOW"
        elif longs and shorts:
            reason = "DIRECTIONAL_CONFLICT"
        elif waits == 3:
            reason = "THREE_AI_WAIT"

        strategies = [str(r.get("strategy", "NO_EDGE")).upper() for r in available.values()]
        regimes = [str(r.get("regime", "UNKNOWN")).upper() for r in available.values()]
        decisions[symbol] = {
            "reviews": reviews,
            "available_reviewers": len(available),
            "actions": actions,
            "strategies": strategies,
            "regimes": regimes,
            "average_confidence": round(sum(confidences)/len(confidences), 2) if confidences else 0.0,
            "final_action": final_action,
            "reason": reason,
        }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {"style":"SCALP_ONLY_24_7","daily_trade_limit":None,"daily_loss_limit":None,"decision_rule":"2_of_3_same_direction_no_opposition"},
        "claude_status": results.get("claude",{}).get("status","ERROR"),
        "deepseek_status": results.get("deepseek",{}).get("status","ERROR"),
        "codex_status": results.get("codex",{}).get("status","ERROR"),
        "symbols": decisions,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True); LOG_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR/"ai_consensus.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    with (LOG_DIR/"ai_consensus.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(out, ensure_ascii=False)+"\n")
    print("="*48); print("V4 THREE-AI SCALP CONSENSUS"); print("="*48)
    print("Claude:", out["claude_status"], "DeepSeek:", out["deepseek_status"], "Codex:", out["codex_status"])
    for s,d in decisions.items():
        print(s, "|", "/".join(d["actions"]), "| FINAL", d["final_action"], "| CONF", d["average_confidence"], "|", d["reason"])


if __name__ == "__main__":
    main()
