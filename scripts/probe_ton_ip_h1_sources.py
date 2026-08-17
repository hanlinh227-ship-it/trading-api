#!/usr/bin/env python3
import json,urllib.parse,urllib.request,time
from datetime import datetime,timezone

def get(url):
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'trading-api-probe/1.0','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode())
 except Exception as e:return {'ERROR':str(e)}

def main():
 end=int(datetime(2026,7,31,23,tzinfo=timezone.utc).timestamp()*1000)
 for s in ('TON','IP'):
  urls={
   'BITGET':'https://api.bitget.com/api/v2/spot/market/history-candles?'+urllib.parse.urlencode({'symbol':s+'USDT','granularity':'1h','endTime':str(end),'limit':'100'}),
   'COINEX':'https://api.coinex.com/v2/spot/kline?'+urllib.parse.urlencode({'market':s+'USDT','period':'1hour','limit':'100'}),
   'MEXC':'https://api.mexc.com/api/v3/klines?'+urllib.parse.urlencode({'symbol':s+'USDT','interval':'1h','limit':'100'}),
  }
  for k,u in urls.items():
   d=get(u);print(s,k,json.dumps(d)[:1500],flush=True);time.sleep(.4)
if __name__=='__main__':main()
