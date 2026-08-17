#!/usr/bin/env python3
import json,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
SYMBOLS='BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC'.split();GATE={'POPCAT','FARTCOIN'};UNAVAILABLE={'TON','IP'}
START=int(datetime(2025,7,1,tzinfo=timezone.utc).timestamp());END=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())-1;OUT='data/provider_snapshots/crypto_4h_jul_dec_2025.json';UA='trading-api-2025-crypto-holdout/1.1'
def get(url,retries=6):
 last=None
 for n in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode())
  except Exception as e:last=e;time.sleep(.7*(n+1))
 raise RuntimeError(str(last))
def okx(s):
 cur=END*1000;ded={};pages=0
 while cur>=START*1000 and pages<35:
  qs=urllib.parse.urlencode({'instId':f'{s}-USDT','bar':'4H','after':str(cur),'limit':'100'});d=get('https://www.okx.com/api/v5/market/history-candles?'+qs)
  if d.get('code')!='0':raise RuntimeError(str(d))
  rows=d.get('data') or []
  if not rows:break
  old=min(int(x[0])//1000 for x in rows)
  for x in rows:
   ts=int(x[0])//1000
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  cur=old*1000-1;pages+=1;time.sleep(.12)
  if old<START:break
 return [ded[k] for k in sorted(ded)],'OKX',pages
def gate(s):
 ded={};cur=START;pages=0;chunk=950*4*3600
 while cur<=END:
  to=min(END,cur+chunk);qs=urllib.parse.urlencode({'currency_pair':f'{s}_USDT','interval':'4h','from':cur,'to':to,'limit':'1000'});d=get('https://api.gateio.ws/api/v4/spot/candlesticks?'+qs)
  if isinstance(d,dict):raise RuntimeError(str(d))
  for x in d or []:
   ts=int(x[0])
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[5]),float(x[3]),float(x[4]),float(x[2])]
  cur=to+1;pages+=1
 return [ded[k] for k in sorted(ded)],'GATE',pages
def one(s):
 if s in UNAVAILABLE:return s,[],'UNAVAILABLE',0
 return s,*(gate(s) if s in GATE else okx(s))
def main():
 data={};diag={};missing={}
 with ThreadPoolExecutor(max_workers=5) as ex:
  fs={ex.submit(one,s):s for s in SYMBOLS}
  for f in as_completed(fs):
   s=fs[f]
   try:
    sym,rows,src,p=f.result()
    # Listing-aware: preserve any real series >= one full month (~180 4H bars).
    if len(rows)<180:
     missing[sym]=f'No full month in Jul-Dec 2025 ({len(rows)} bars)';print('NO_FULL_MONTH',sym,len(rows),flush=True);continue
    data[sym]=rows;diag[sym]={'source':src,'bars':len(rows),'first':rows[0][0],'last':rows[-1][0],'pages':p};print('HOLDOUT',sym,src,len(rows),rows[0][0],flush=True)
   except Exception as e:missing[s]=str(e);print('FAIL',s,e,flush=True)
 if len(data)<50:raise RuntimeError('Insufficient independent coverage '+json.dumps(missing))
 doc={'version':'CRYPTO_4H_JUL_DEC_2025_V2_LISTING_AWARE','interval':'4h','requestedSymbols':SYMBOLS,'coverageCount':len(data),'coveredSymbols':sorted(data),'missingSymbols':missing,'startDate':'2025-07-01','endDate':'2025-12-31','independentFrom2026MethodDesign':True,'listingAware':True,'sources':{x:sum(1 for q in diag.values() if q['source']==x) for x in ('OKX','GATE')},'diagnostics':diag,'data':data};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({'status':'OK_PARTIAL','coverage':len(data),'missing':missing,'sources':doc['sources']},indent=2),flush=True)
if __name__=='__main__':main()
