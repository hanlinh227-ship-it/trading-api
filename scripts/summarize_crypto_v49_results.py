#!/usr/bin/env python3
import json,os,re,subprocess,sys
TARGETS='AAVE ALGO ARB AVAX DOT FIL FLOKI INJ JUP LDO LINK MOODENG NEAR ONDO POL S SUI WIF WLD XPL'.split()

def main():
    out={}
    for s in TARGETS:
        env=dict(os.environ);env['TARGET_SYMBOL']=s;env['PYTHONPATH']='.'
        p=subprocess.run([sys.executable,'scripts/offline_crypto_remaining20_v49_matrix.py'],env=env,capture_output=True,text=True,timeout=90)
        lines=[x for x in p.stdout.splitlines() if x.startswith('FINAL ')]
        if p.returncode!=0 or not lines:
            out[s]={'status':'ERROR','stderr':p.stderr[-500:]};print('SUM',s,'ERROR',flush=True);continue
        d=json.loads(lines[-1][6:]);f=d.get('frozen');out[s]={'status':d['status'],'stage':f.get('stage') if f else None,'final':f.get('final') if f else None,'params':f.get('params') if f else None};print('SUM',s,out[s]['status'],out[s]['final'],flush=True)
    passed=[s for s,v in out.items() if v['status']=='PASS'];failed=[s for s,v in out.items() if v['status']!='PASS']
    print('SUMMARY_JSON '+json.dumps({'passed':passed,'failed':failed,'count':len(passed),'results':out}),flush=True)
if __name__=='__main__':main()
