#!/usr/bin/env python3
"""Diagnose the exact bust trade of BTC V4 best config without changing execution rules."""
import csv,io,urllib.request
from datetime import datetime,timedelta,timezone
URL='https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Crypto/BTCUSD/BTCUSD_M5.csv'

def load():
 req=urllib.request.Request(URL,headers={'User-Agent':'btc-v4-diag'})
 with urllib.request.urlopen(req,timeout=120) as r:text=r.read().decode('utf-8-sig')
 a=[]
 for x in csv.DictReader(io.StringIO(text)):
  try:
   raw=(x.get('time') or x.get('datetime')).strip().replace('T',' ').replace('Z','')[:19];d=datetime.strptime(raw,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
   a.append([int(d.timestamp()),raw,float(x['open']),float(x['high']),float(x['low']),float(x['close'])])
  except:pass
 a.sort();cut=a[-1][0]-183*86400;return [x for x in a if x[0]>=cut]
def ema(v,n):
 k=2/(n+1);o=[v[0]]
 for x in v[1:]:o.append(k*x+(1-k)*o[-1])
 return o
def rsi(v,n=14):
 o=[50.]*len(v);g=[max(v[i]-v[i-1],0) for i in range(1,len(v))];l=[max(v[i-1]-v[i],0) for i in range(1,len(v))]
 ag=sum(g[:n])/n;al=sum(l[:n])/n;o[n]=100 if al==0 else 100-100/(1+ag/al)
 for i in range(n+1,len(v)):
  ag=(ag*(n-1)+g[i-1])/n;al=(al*(n-1)+l[i-1])/n;o[i]=100 if al==0 else 100-100/(1+ag/al)
 return o
def atr(b,n=14):
 t=[]
 for i,x in enumerate(b):
  p=b[i-1][5] if i else x[5];t.append(max(x[3]-x[4],abs(x[3]-p),abs(x[4]-p)))
 o=[]
 for i,x in enumerate(t):o.append(x if i==0 else (sum(t[:i+1])/(i+1) if i<n else (o[-1]*(n-1)+x)/n))
 return o

def main():
 b=load();cl=[x[5] for x in b];e5=ema(cl,5);e20=ema(cl,20);e60=ema(cl,60);e150=ema(cl,150);e240=ema(cl,240);e600=ema(cl,600);rr=rsi(cl);aa=atr(b)
 # exact V4 winner: breakout 5/20, lookback 48, RSI 48..70, HTF=1 (M15 proxy 60/150), both directions
 bal=20.;lot=.02;tp=300.;pos=None;cool=-1;tps=0;tr=0
 for i in range(622,len(b)):
  x=b[i]
  if pos is None:
   if i<=cool:continue
   j=i-1
   up=e5[j]>e20[j] and e5[j]>e5[j-2] and e60[j]>e150[j] and e60[j]>e60[j-3]
   dn=e5[j]<e20[j] and e5[j]<e5[j-2] and e60[j]<e150[j] and e60[j]<e60[j-3]
   hi=max(z[3] for z in b[j-48:j]);lo=min(z[4] for z in b[j-48:j]);d=0
   if up and b[j][5]>hi and 48<=rr[j]<=70:d=1
   if dn and b[j][5]<lo and 30<=rr[j]<=52:d=-1
   if not d:continue
   pos=[d,x[2],lot,i];tr+=1
   print(f'OPEN trade={tr} lot={lot:.2f} time={x[1]} side={"LONG" if d>0 else "SHORT"} entry={x[2]:.2f} atr={aa[j]:.2f} rsi={rr[j]:.2f} m5ema5={e5[j]:.2f} ema20={e20[j]:.2f} m15proxy60={e60[j]:.2f} proxy150={e150[j]:.2f} h1ema240={e240[j]:.2f} h1ema600={e600[j]:.2f}')
  d,en,L,ei=pos;ad=max(0.,en-x[4]) if d>0 else max(0.,x[3]-en);flt=bal-ad*L
  if flt<=0:
   print(f'BUST trade={tr} afterTP={tps} lot={L:.2f} bustTime={x[1]} side={"LONG" if d>0 else "SHORT"} entry={en:.2f} adverse={ad:.2f} balanceBefore=${bal:.2f} high={x[3]:.2f} low={x[4]:.2f}')
   # print market diagnostics around entry, all computed from already-known values at each bar
   for k in [ei-12,ei-6,ei-1,ei, min(i,ei+12),i]:
    if 0<=k<len(b):print(f'CTX time={b[k][1]} close={b[k][5]:.2f} atr={aa[k]:.2f} rsi={rr[k]:.2f} e5-e20={e5[k]-e20[k]:.2f} e60-e150={e60[k]-e150[k]:.2f} e240-e600={e240[k]-e600[k]:.2f}')
   return
  tar=en+d*tp;hit=x[3]>=tar if d>0 else x[4]<=tar
  if hit:
   bal+=tp*L;tps+=1;print(f'TP trade={tr} lot={L:.2f} time={x[1]} bal=${bal:.2f}')
   lot=round(L+.01,2);pos=None;cool=i+1
if __name__=='__main__':main()
