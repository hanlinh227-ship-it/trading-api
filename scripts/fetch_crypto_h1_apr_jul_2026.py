#!/usr/bin/env python3
import json,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path

SYMBOLS='BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC'.split()
GATE={'POPCAT','FARTCOIN'};KUCOIN={'TON','IP'}
START=int(datetime(2026,4,1,tzinfo=timezone.utc).timestamp());END=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp())-1
OUT='data/provider_snapshots/crypto_h1_apr_jul_2026.json';UA='trading-api-h1-snapshot/1.0'

def get(url,retries=6,timeout=25):
 last=None
 for n in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())
  except Exception as e:last=e;time.sleep(.8*(n+1))
 raise RuntimeError(str(last))

def okx(sym):
 cursor=END*1000;ded={};pages=0
 while cursor>=START*1000 and pages<60:
  qs=urllib.parse.urlencode({'instId':f'{sym}-USDT','bar':'1H','after':str(cursor),'limit':'100'});d=get('https://www.okx.com/api/v5/market/history-candles?'+qs)
  if d.get('code')!='0':raise RuntimeError(f'OKX {d}')
  rows=d.get('data') or []
  if not rows:break
  oldest=min(int(x[0])//1000 for x in rows)
  for x in rows:
   ts=int(x[0])//1000
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  cursor=oldest*1000-1;pages+=1;time.sleep(.12)
  if oldest<START:break
 return [ded[k] for k in sorted(ded)],'OKX',pages

def gate(sym):
 ded={};cur=START;pages=0;chunk=900*3600
 while cur<=END:
  to=min(END,cur+chunk);qs=urllib.parse.urlencode({'currency_pair':f'{sym}_USDT','interval':'1h','from':cur,'to':to,'limit':'1000'});d=get('https://api.gateio.ws/api/v4/spot/candlesticks?'+qs)
  if isinstance(d,dict):raise RuntimeError(f'GATE {d}')
  for x in d or []:
   ts=int(x[0])
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[5]),float(x[3]),float(x[4]),float(x[2])]
  cur=to+1;pages+=1;time.sleep(.20)
 return [ded[k] for k in sorted(ded)],'GATE',pages

def kucoin(sym):
 ded={};cur=START;pages=0;chunk=1400*3600
 while cur<=END:
  to=min(END,cur+chunk);qs=urllib.parse.urlencode({'symbol':f'{sym}-USDT','type':'1hour','startAt':cur,'endAt':to});d=get('https://api.kucoin.com/api/v1/market/candles?'+qs)
  if d.get('code')!='200000':raise RuntimeError(f'KUCOIN {d}')
  rows=d.get('data') or []
  for x in rows:
   ts=int(x[0])
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[3]),float(x[4]),float(x[2])]
  cur=to+1;pages+=1;time.sleep(.20)
 return [ded[k] for k in sorted(ded)],'KUCOIN',pages

def one(s):
 if s in GATE:r=gate(s)
 elif s in KUCOIN:r=kucoin(s)
 else:r=okx(s)
 return s,*r

def main():
 data={};diag={};errors={}
 with ThreadPoolExecutor(max_workers=5) as ex:
  fs={ex.submit(one,s):s for s in SYMBOLS}
  for f in as_completed(fs):
   s=fs[f]
   try:
    sym,rows,src,pages=f.result()
    if len(rows)<2000:raise RuntimeError(f'too few H1 bars {len(rows)}')
    if rows[0][0][:10]>'2026-04-05' or rows[-1][0][:10]<'2026-07-28':raise RuntimeError(f'coverage {rows[0][0]} {rows[-1][0]}')
    data[sym]=rows;diag[sym]={'source':src,'bars':len(rows),'first':rows[0][0],'last':rows[-1][0],'pages':pages};print('H1',sym,src,len(rows),flush=True)
   except Exception as e:errors[s]=str(e);print('FAIL',s,e,flush=True)
 if errors or len(data)!=61:raise RuntimeError('coverage failed '+json.dumps(errors))
 doc={'version':'CRYPTO_H1_APR_JUL_2026_V1','interval':'1h','coverageCount':61,'requestedSymbols':SYMBOLS,'startDate':'2026-04-01','endDate':'2026-07-31','sources':{x:sum(1 for q in diag.values() if q['source']==x) for x in ('OKX','GATE','KUCOIN')},'diagnostics':diag,'data':data}
 Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({'status':'OK','coverage':61,'sources':doc['sources'],'bars':sum(q['bars'] for q in diag.values())},indent=2),flush=True)
if __name__=='__main__':main()
