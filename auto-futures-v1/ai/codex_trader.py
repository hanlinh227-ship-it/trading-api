import json
import os
import subprocess
from common import load_snapshot, candidate_setups, compact_setup, parse_review_response, role_prompt

MODEL=os.environ.get('CODEX_REVIEW_MODEL','gpt-5.6-sol')
TIMEOUT_SECONDS=int(os.environ.get('CODEX_REVIEW_TIMEOUT_SECONDS','46'))
ROLE='''
You are CODEX, the quantitative/logical execution verifier in a Binance perpetual SCALP council.
Specialty: deterministic consistency — timeframe alignment, strategy/regime compatibility, stop geometry versus volatility/noise, target distance versus costs, spread, and numerical execution coherence.
Do not duplicate regime narrative or speculative risk commentary. Verify math and internal consistency.
Do not reverse casually; normally WAIT if the proposed direction fails verification.
'''
PROMPT=role_prompt(ROLE)

def main():
    snap=load_snapshot();setups=[compact_setup(x) for x in candidate_setups(snap)]
    if not setups:
        print(json.dumps({'status':'OK','model':MODEL,'review_count':0,'reviews':{},'transport':'CODEX_CLI'}));return
    payload=PROMPT+'\nMARKET_DATA='+json.dumps(setups,ensure_ascii=False,separators=(',',':'))
    cmd=['/usr/bin/codex','exec','--model',MODEL,'--ephemeral','--sandbox','read-only','--skip-git-repo-check',payload]
    try:p=subprocess.run(cmd,capture_output=True,text=True,timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(json.dumps({'status':'TIMEOUT','timeout_seconds':TIMEOUT_SECONDS,'reviews':{},'transport':'CODEX_CLI'}));return
    except Exception as exc:
        print(json.dumps({'status':'ERROR','error':repr(exc),'reviews':{},'transport':'CODEX_CLI'}));return
    if p.returncode!=0:
        print(json.dumps({'status':'ERROR','error':p.stderr[-900:],'reviews':{},'transport':'CODEX_CLI'}));return
    clean,status=parse_review_response(p.stdout.strip(),setups)
    print(json.dumps({'status':status,'model':MODEL,'review_count':len(clean),'reviews':clean,'transport':'CODEX_CLI_PINNED'},ensure_ascii=False))

if __name__=='__main__':main()
