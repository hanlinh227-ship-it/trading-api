#!/usr/bin/env python3
import json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
SYMS=['BTC','ETH','SOL'];START=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp());END=int(datetime(2026,4,1,tzinfo=timezone.utc).timestamp())-1;OUT='data/provider_snapshots/crypto_context_h1_jan_mar_2026.json'
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'trading-api-context/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode())
def fetch(s):
 cur=END*1000;ded={}
 while cur>=START*1000:
  qs=urllib.parse.urlencode({'instId':f'{s}-USDT','bar':'1H','after':str(cur),'limit':'100'});d=get('https://www.okx.com/api/v5/market/history-candles?'+qs);rows=d.get('data') or []
  if not rows:break
  old=min(int(x[0])//1000 for x in rows)
  for x in rows:
   ts=int(x[0])//1000
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  cur=old*1000-1;time.sleep(.08)
  if old<START:break
 return [ded[k] for k in sorted(ded)]
def main():
 data={s:fetch(s) for s in SYMS}
 if any(len(v)<2100 for v in data.values()):raise RuntimeError(str({s:len(v) for s,v in data.items()}))
 doc={'version':'CRYPTO_CONTEXT_H1_JAN_MAR_2026_V1','symbols':SYMS,'data':data,'diagnostics':{s:{'bars':len(v),'first':v[0][0],'last':v[-1][0]} for s,v in data.items()}};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps(doc['diagnostics'],indent=2))
if __name__=='__main__':main()
