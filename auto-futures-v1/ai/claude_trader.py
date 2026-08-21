import json
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, parse_review_response, role_prompt

MODEL = "sonnet"
TIMEOUT_SECONDS = 50
ROLE = """
You are CLAUDE, the market-context/regime reviewer for Binance USDT perpetual scalps.
Your specialty is context coherence: higher-timeframe pressure, regime fit, chase/exhaustion risk, and whether the execution trigger makes sense inside that context.
Use 1d/4h/1h for higher-timeframe pressure, 30m/15m for regime/setup, and 5m/3m/1m for trigger quality.
Do not duplicate the other reviewers by inventing portfolio/risk constraints. Focus on context/regime consistency and timing quality.
"""
PROMPT = role_prompt(ROLE)


def main():
    snap = load_snapshot()
    setups = [compact_setup(x) for x in candidate_setups(snap)]
    if not setups:
        print(json.dumps({"status":"OK","model":MODEL,"review_count":0,"reviews":{}})); return
    payload = PROMPT + "\nDATA=" + json.dumps(setups, ensure_ascii=False, separators=(",", ":"))
    try:
        p = subprocess.run(["claude", "--model", MODEL, "-p", payload], capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(json.dumps({"status":"TIMEOUT","timeout_seconds":TIMEOUT_SECONDS,"reviews":{}})); return
    except Exception as exc:
        print(json.dumps({"status":"ERROR","error":repr(exc),"reviews":{}})); return
    if p.returncode != 0:
        print(json.dumps({"status":"ERROR","error":p.stderr[-700:],"reviews":{}})); return
    clean,status=parse_review_response(p.stdout.strip(),setups)
    print(json.dumps({"status":status,"model":MODEL,"review_count":len(clean),"reviews":clean}, ensure_ascii=False))

if __name__ == "__main__":
    main()
