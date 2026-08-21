import json
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, parse_review_response, role_prompt

MODEL = "gpt-5.6-sol"
TIMEOUT_SECONDS = 50
ROLE = """
You are CODEX, the quantitative/logical execution verifier in a Binance perpetual SCALP council.
Your specialty is deterministic consistency: timeframe alignment, strategy/regime compatibility, stop geometry versus volatility/noise, target distance versus costs, spread, and whether the supplied numbers logically support execution.
Do not duplicate market-regime narrative or adversarial speculation. Verify math, internal consistency and execution logic.
Do not reverse direction casually. If the proposed direction fails verification, normally return WAIT.
"""
PROMPT = role_prompt(ROLE)


def main():
    snap = load_snapshot()
    setups = [compact_setup(x) for x in candidate_setups(snap)]
    if not setups:
        print(json.dumps({"status":"OK","model":MODEL,"review_count":0,"reviews":{}})); return
    payload = PROMPT + "\nDATA=" + json.dumps(setups, ensure_ascii=False, separators=(",", ":"))
    try:
        p = subprocess.run(["/usr/bin/codex", "exec", payload], capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(json.dumps({"status":"TIMEOUT","timeout_seconds":TIMEOUT_SECONDS,"reviews":{}})); return
    except Exception as exc:
        print(json.dumps({"status":"ERROR","error":repr(exc),"reviews":{}})); return
    if p.returncode != 0:
        print(json.dumps({"status":"ERROR","error":p.stderr[-900:],"reviews":{}})); return
    clean,status=parse_review_response(p.stdout.strip(),setups)
    print(json.dumps({"status":status,"model":MODEL,"review_count":len(clean),"reviews":clean}, ensure_ascii=False))

if __name__ == "__main__":
    main()
