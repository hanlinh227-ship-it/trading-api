#!/usr/bin/env python3
import json, math, urllib.parse, urllib.request, time
from datetime import datetime, timezone

OKX_BASE="https://www.okx.com"
# Current Breakout screener universe captured 2026-08-17. Forced MARKET test: no WAIT/LIMIT.
COINS="BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC".split()
TF={"D1":"1Dutc","H4":"4H","H1":"1H","M15":"15m","M5":"5m"}
TF_MS={"D1":86400000,"H4":14400000,"H1":3600000,"M15":900000,"M5":300000}
CUTOFF="2026-08-10T12:00:00Z"
MAX_FORWARD_HOURS=72

def iso_ms(s):return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)
def ms_iso(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat().replace("+00:00","Z")
def http(url):
 req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"breakout-blind-v3"})
 for n in range(4):
  try:
   with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode())
  except Exception:
   if n==3:raise
   time.sleep(0.8*(n+1))
def fv(x):
 try:
  v=float(x);return v if math.isfinite(v) else None
 except:return None
def rows(rows):
 a=[]
 for r in rows:
  ts=int(r[0]);a.append({"ts":ts,"datetime":ms_iso(ts),"open":fv(r[1]),"high":fv(r[2]),"low":fv(r[3]),"close":fv(r[4]),"volume":fv(r[5])})
 return sorted([x for x in a if x["close"] is not None],key=lambda x:x["ts"])
def hist(inst,bar,cut,limit=300):
 u=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar={bar}&after={cut}&limit={limit}"
 return rows(http(u).get("data") or [])
def future_page(inst,before,after):
 u=f"{OKX_BASE}/api/v5/market/history-candles?instId={urllib.parse.quote(inst)}&bar=5m&before={before}&after={after}&limit=300"
 return rows(http(u).get("data") or [])
def ema(v,p):
 if len(v)<p:return None
 x=sum(v[:p])/p;k=2/(p+1)
 for z in v[p:]:x=z*k+x*(1-k)
 return x
def rsi(v,p=14):
 if len(v)<=p:return None
 g=l=0
 for i in range(1,p+1):d=v[i]-v[i-1];g+=max(d,0);l+=max(-d,0)
 g/=p;l/=p
 for i in range(p+1,len(v)):d=v[i]-v[i-1];g=(g*(p-1)+max(d,0))/p;l=(l*(p-1)+max(-d,0))/p
 return 100 if l==0 else 100-100/(1+g/l)
def atr(c,p=14):
 if len(c)<=p:return None
 tr=[max(c[i]["high"]-c[i]["low"],abs(c[i]["high"]-c[i-1]["close"]),abs(c[i]["low"]-c[i-1]["close"])) for i in range(1,len(c))]
 x=sum(tr[:p])/p
 for z in tr[p:]:x=(x*(p-1)+z)/p
 return x
def summ(c):
 v=[x["close"] for x in c];cl=v[-1];e20,e50,e200=ema(v,20),ema(v,50),ema(v,200);rr=rsi(v);aa=atr(c)
 trend="neutral"
 if e20 and e50:
  if cl>e20>e50:trend="bullish"
  elif cl<e20<e50:trend="bearish"
 vol=[x["volume"] or 0 for x in c[-21:]];base=sum(vol[:-1])/max(1,len(vol)-1);vr=(vol[-1]/base if base else 1)
 dist=((cl-e20)/aa if e20 and aa else 0)
 return {"close":cl,"ema20":e20,"ema50":e50,"ema200":e200,"rsi14":rr,"atr14":aa,"trend":trend,"dist20ATR":dist,"volumeRatio":vr}
def structure(c,n=20):
 x=c[-n:];mid=max(2,n//2);a=x[:mid];b=x[mid:]
 hh=max(z["high"] for z in b)>max(z["high"] for z in a);hl=min(z["low"] for z in b)>min(z["low"] for z in a)
 lh=max(z["high"] for z in b)<max(z["high"] for z in a);ll=min(z["low"] for z in b)<min(z["low"] for z in a)
 return 1 if hh and hl else -1 if lh and ll else 0
def score(sums,frames):
 w={"D1":3.2,"H4":3.0,"H1":2.4,"M15":1.5,"M5":0.9};sc=0;parts={}
 for k,wt in w.items():
  s=sums[k];q=0
  q += 1 if s["trend"]=="bullish" else -1 if s["trend"]=="bearish" else 0
  if s["ema200"] is not None:q += .35 if s["close"]>s["ema200"] else -.35
  if s["rsi14"] is not None:q += .25 if s["rsi14"]>=55 else -.25 if s["rsi14"]<=45 else 0
  st=structure(frames[k]);q += .35*st
  sc+=wt*q;parts[k]=round(wt*q,3)
 # Crypto-specific execution modifiers: volume conviction, exhaustion/chase, LTF impulse.
 m15,m5=sums["M15"],sums["M5"]
 sc += .45*min(2,max(.5,m15["volumeRatio"]))*(1 if m15["close"]>=m15["ema20"] else -1)
 sc += .30*min(2,max(.5,m5["volumeRatio"]))*(1 if m5["close"]>=m5["ema20"] else -1)
 # Anti-chase does not create WAIT; it weakens an overextended direction so the opposite may win.
 for s,pen in ((sums["H1"],1.3),(m15,.8)):
  if s["dist20ATR"]>1.4:sc-=pen
  elif s["dist20ATR"]<-1.4:sc+=pen
 if (m15["rsi14"] or 50)>72:sc-=1.0
 if (m15["rsi14"] or 50)<28:sc+=1.0
 return sc,parts
def choose(sums,frames):
 sc,parts=score(sums,frames);side="BUY" if sc>=0 else "SELL";entry=frames["M5"][-1]["close"]
 # Structure-first stop; ATR floor prevents micro stop. Forced market still uses valid invalidation.
 a=sums["M15"]["atr14"] or entry*.01;recent=frames["M15"][-12:]
 if side=="BUY":sl=min(min(x["low"] for x in recent),entry-1.25*a);tp=entry+1.5*(entry-sl)
 else:sl=max(max(x["high"] for x in recent),entry+1.25*a);tp=entry-1.5*(sl-entry)
 return side,sc,entry,sl,tp,parts
def evaluate(inst,side,entry,sl,tp,cut):
 # Continue until TP or SL, capped at 72h so every usable test has a resolved result.
 end=cut+MAX_FORWARD_HOURS*3600000;cursor=cut;mfe=mae=0;seen=0
 while cursor<end:
  nxt=min(end,cursor+24*3600000);cs=future_page(inst,cursor,nxt)
  cs=[x for x in cs if cursor<=x["ts"]<nxt];seen+=len(cs)
  for x in cs:
   if side=="BUY":mfe=max(mfe,x["high"]-entry);mae=max(mae,entry-x["low"]);hs=x["low"]<=sl;ht=x["high"]>=tp
   else:mfe=max(mfe,entry-x["low"]);mae=max(mae,x["high"]-entry);hs=x["high"]>=sl;ht=x["low"]<=tp
   if hs and ht:return {"result":"AMBIGUOUS","mfe":mfe,"mae":mae,"candles":seen}
   if hs:return {"result":"SL","mfe":mfe,"mae":mae,"candles":seen}
   if ht:return {"result":"TP","mfe":mfe,"mae":mae,"candles":seen}
  cursor=nxt
 return {"result":"UNRESOLVED_72H","mfe":mfe,"mae":mae,"candles":seen}
def run(sym):
 inst=f"{sym}-USDT";cut=iso_ms(CUTOFF);frames={};sums={}
 for k,b in TF.items():
  c=[x for x in hist(inst,b,cut) if x["ts"]+TF_MS[k]<=cut]
  if len(c)<60:raise RuntimeError(f"{k} insufficient:{len(c)}")
  frames[k]=c;sums[k]=summ(c)
 side,sc,en,sl,tp,parts=choose(sums,frames);out=evaluate(inst,side,en,sl,tp,cut)
 return {"symbol":sym+"USDT","cutoff":CUTOFF,"source":"OKX historical REST","blind":True,"decision":side,"score":round(sc,3),"entry":en,"sl":sl,"tp1_5R":tp,"scoreParts":parts,"snapshot":sums,"outcome":out}
def main():
 res=[]
 for sym in COINS:
  try:res.append(run(sym))
  except Exception as e:res.append({"symbol":sym+"USDT","cutoff":CUTOFF,"error":str(e)})
 usable=[r for r in res if r.get("decision") in ("BUY","SELL")];resolved=[r for r in usable if r.get("outcome",{}).get("result") in ("TP","SL")];wins=sum(r["outcome"]["result"]=="TP" for r in resolved);loss=sum(r["outcome"]["result"]=="SL" for r in resolved)
 payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V3 forced-market strict blind; D1/H4/H1/M15/M5 trend+EMA200+RSI+structure+volume; ATR anti-chase/exhaustion; structure SL; TP=1.5R; no WAIT/LIMIT; future hidden until decision; resolve up to 72h","universeRequested":len(COINS),"tests":res,"summary":{"requested":len(COINS),"marketTrades":len(usable),"dataErrors":len(res)-len(usable),"resolved":len(resolved),"wins":wins,"losses":loss,"unresolved":len(usable)-len(resolved),"winRateResolved":round(100*wins/len(resolved),2) if resolved else None,"expectancyR":round((wins*1.5-loss)/len(resolved),3) if resolved else None}}
 with open("data/blind_backtest.json","w") as f:json.dump(payload,f,indent=2)
 print(json.dumps(payload["summary"],indent=2))
if __name__=="__main__":main()
