import {forexAutoConfig} from "./forex-auto-config.js";
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const ema=(a,p)=>{if(!a.length)return 0;const k=2/(p+1);let e=a[0];for(const x of a.slice(1))e=x*k+e*(1-k);return e};
function atr(rows,p=14){if(rows.length<2)return 0;const tr=[];for(let i=1;i<rows.length;i++){const h=n(rows[i].high),l=n(rows[i].low),pc=n(rows[i-1].close);tr.push(Math.max(h-l,Math.abs(h-pc),Math.abs(l-pc)));}return avg(tr.slice(-p));}
function rsi(rows,p=14){const c=rows.map(x=>n(x.close));if(c.length<p+1)return 50;let g=0,l=0;for(let i=c.length-p;i<c.length;i++){const d=c[i]-c[i-1];if(d>0)g+=d;else l-=d;}if(l===0)return 100;const rs=(g/p)/(l/p);return 100-100/(1+rs);}
function swing(rows,side,look=12){const x=rows.slice(-look);return side==="Buy"?Math.min(...x.map(r=>n(r.low,Infinity))):Math.max(...x.map(r=>n(r.high,-Infinity)));}
function pipSize(symbol){if(symbol==="XAUUSD")return .01;return /JPY$/.test(symbol)?.01:.0001;}
function spreadPips(s){const pip=pipSize(String(s.symbol||"").toUpperCase());return pip>0?(n(s.ask)-n(s.bid))/pip:999;}
function bars(s,tf){return Array.isArray(s?.bars?.[tf])?s.bars[tf]:[];}
function profile(symbol){if(symbol==="EURGBP")return {family:"RANGE_FX",minTrend:.18,maxChase:.35};if(/GBPJPY|EURJPY/.test(symbol))return {family:"JPY_MOMENTUM",minTrend:.24,maxChase:.55};if(symbol==="XAUUSD")return {family:"XAU_LIQUIDITY",minTrend:.22,maxChase:.60};if(/AUDUSD|NZDUSD/.test(symbol))return {family:"ASIA_COMMODITY_FX",minTrend:.18,maxChase:.45};if(/GBPUSD|USDJPY|USDCAD/.test(symbol))return {family:"MOMENTUM_MAJOR",minTrend:.20,maxChase:.50};return {family:"STABLE_MAJOR",minTrend:.16,maxChase:.42};}
function sideFrom(fast,slow){return fast>slow?"Buy":fast<slow?"Sell":null;}
function priceAction(rows,side,a){
 const x=rows.slice(-20);if(x.length<8)return {score:0,tags:[]};const last=x[x.length-1],prev=x[x.length-2],prior=x.slice(0,-2),tags=[];let score=0;
 const priorLow=Math.min(...prior.map(r=>n(r.low))),priorHigh=Math.max(...prior.map(r=>n(r.high))),body=Math.abs(n(last.close)-n(last.open)),range=Math.max(n(last.high)-n(last.low),1e-12);
 const bullSweep=n(last.low)<priorLow&&n(last.close)>priorLow,bearSweep=n(last.high)>priorHigh&&n(last.close)<priorHigh;
 if((side==="Buy"&&bullSweep)||(side==="Sell"&&bearSweep)){score+=5;tags.push("LIQUIDITY_SWEEP");}
 const displacement=body/Math.max(a,1e-12)>.55&&body/range>.55&&((side==="Buy"&&n(last.close)>n(last.open))||(side==="Sell"&&n(last.close)<n(last.open)));
 if(displacement){score+=4;tags.push("DISPLACEMENT");}
 const bos=side==="Buy"?n(last.close)>n(prev.high):n(last.close)<n(prev.low);if(bos){score+=4;tags.push("MICRO_BOS_MSS");}
 if(x.length>=3){const a0=x[x.length-3],gap=side==="Buy"?n(last.low)>n(a0.high):n(last.high)<n(a0.low);if(gap){score+=3;tags.push("FVG_IMBALANCE");}}
 const rejection=side==="Buy"?(Math.min(n(last.open),n(last.close))-n(last.low))/range:(n(last.high)-Math.max(n(last.open),n(last.close)))/range;if(rejection>.35){score+=2;tags.push("REJECTION_WICK");}
 return {score:Math.min(12,score),tags};
}
function locationContext(rows,side,entry){const x=rows.slice(-30);if(!x.length)return {score:0,tags:[]};const hi=Math.max(...x.map(r=>n(r.high))),lo=Math.min(...x.map(r=>n(r.low))),mid=(hi+lo)/2,tags=[];let score=0;if(side==="Buy"&&entry<=mid){score+=2;tags.push("DISCOUNT_LOCATION");}if(side==="Sell"&&entry>=mid){score+=2;tags.push("PREMIUM_LOCATION");}return {score,tags,rangeHigh:hi,rangeLow:lo,rangeMid:mid};}
export function buildForexCandidate(env,s){
 const c=forexAutoConfig(env),m5=bars(s,"M5"),m15=bars(s,"M15"),h1=bars(s,"H1"),h4=bars(s,"H4"),symbol=String(s.symbol||"").toUpperCase(),pf=profile(symbol);
 if(m5.length<30||m15.length<30||h1.length<30||(c.marketData.requireH4&&h4.length<30))return {ok:false,reason:"INSUFFICIENT_BARS",symbol:s.symbol};
 const ts=Number(s.timestamp||0),tsMs=ts>1e12?ts:ts*1000,ageSec=tsMs>0?(Date.now()-tsMs)/1000:Infinity;if(ageSec<0||ageSec>c.marketData.maxQuoteAgeSec)return {ok:false,reason:"STALE_QUOTE",symbol:s.symbol,quoteAgeSec:ageSec};
 const a5=atr(m5),a15=atr(m15),a1h=atr(h1),a4h=atr(h4),h4c=h4.map(x=>n(x.close)),h1c=h1.map(x=>n(x.close)),m15c=m15.map(x=>n(x.close)),m5c=m5.map(x=>n(x.close));
 const h4fast=ema(h4c.slice(-40),20),h4slow=ema(h4c.slice(-60),50),fast=ema(h1c.slice(-40),20),slow=ema(h1c.slice(-60),50),mfast=ema(m15c.slice(-30),12),mslow=ema(m15c.slice(-40),26),m5ema=ema(m5c.slice(-30),20),rrsi=rsi(m5);
 const h4Trend=sideFrom(h4fast,h4slow),h1Trend=sideFrom(fast,slow),m15Trend=sideFrom(mfast,mslow),trend=h4Trend&&h4Trend===h1Trend&&h1Trend===m15Trend?h1Trend:null;
 if(!trend)return {ok:false,reason:"NO_H4_H1_M15_ALIGNMENT",symbol:s.symbol,h4Trend,h1Trend,m15Trend};
 const h4Strength=Math.abs(h4fast-h4slow)/Math.max(a4h,1e-12),trendStrength=(h4Strength+Math.abs(fast-slow)/Math.max(a1h,1e-12)+Math.abs(mfast-mslow)/Math.max(a15,1e-12))/3;if(trendStrength<pf.minTrend)return {ok:false,reason:"REGIME_TOO_WEAK",symbol:s.symbol,trendStrength,family:pf.family};
 const sp=spreadPips(s),spCap=symbol==="XAUUSD"?c.risk.maxSpreadPips.XAU:/JPY$/.test(symbol)?c.risk.maxSpreadPips.JPY:c.risk.maxSpreadPips.FX;if(sp>spCap)return {ok:false,reason:"SPREAD_TOO_WIDE",symbol:s.symbol,spreadPips:sp,spreadCap:spCap};
 const entry=trend==="Buy"?n(s.ask):n(s.bid),chaseAtr=Math.abs(entry-m5ema)/Math.max(a5,1e-12),maxChase=Math.min(c.risk.maxChaseAtr,pf.maxChase);if(chaseAtr>maxChase)return {ok:false,reason:"PRICE_TOO_EXTENDED_WAIT_RETEST",symbol:s.symbol,chaseAtr,maxChase};
 const pullback=trend==="Buy"?rrsi>=42&&rrsi<=64:rrsi>=36&&rrsi<=58;if(!pullback)return {ok:false,reason:"NO_HEALTHY_PULLBACK",symbol:s.symbol,rsi:rrsi};
 const rawSwing=swing(m15,trend),buffer=Math.max(a5*c.risk.structureBufferAtr,a15*.10),minStop=Math.max(a5*c.risk.minStopAtr,a15*.55),maxStop=Math.max(a5*c.risk.maxStopAtr,a15*1.8);let sl=trend==="Buy"?rawSwing-buffer:rawSwing+buffer;let stopDist=Math.abs(entry-sl);if(stopDist<minStop){sl=trend==="Buy"?entry-minStop:entry+minStop;stopDist=minStop;}if(stopDist>maxStop)return {ok:false,reason:"STOP_TOO_WIDE",symbol:s.symbol,stopAtr:stopDist/Math.max(a5,1e-12)};
 const structureTarget=trend==="Buy"?Math.max(...m15.slice(-20).map(x=>n(x.high))):Math.min(...m15.slice(-20).map(x=>n(x.low))),rrStruct=Math.abs(structureTarget-entry)/Math.max(stopDist,1e-12);if(rrStruct<c.risk.minRR)return {ok:false,reason:"STRUCTURE_RR_TOO_LOW",symbol:s.symbol,rrStruct};const rr=Math.max(c.risk.minRR,Math.min(2.6,rrStruct)),tp=trend==="Buy"?entry+stopDist*rr:entry-stopDist*rr;
 const regime=trendStrength>=.55?"STRONG_TREND":trendStrength>=.30?"TREND":"SOFT_TREND",setup=chaseAtr<=.18?"TREND_PULLBACK":chaseAtr<=.32?"RETEST_CONTINUATION":"LATE_RETEST";
 // Advanced concepts are SOFT EVIDENCE: they improve ranking/confidence but never become mandatory gates.
 const pa5=priceAction(m5,trend,a5),pa15=priceAction(m15,trend,a15),loc=locationContext(m15,trend,entry),advancedTags=[...new Set([...pa5.tags,...pa15.tags,...loc.tags])],advancedScore=Math.min(14,Math.round(pa5.score*.55+pa15.score*.65+loc.score));
 let score=65;score+=Math.min(12,trendStrength*15);score+=rr>=2?6:2;score+=sp<spCap*.5?4:1;score+=trend==="Buy"?(rrsi>48?3:0):(rrsi<52?3:0);score-=Math.max(0,(chaseAtr-.18)*12);if(setup==="LATE_RETEST")score-=4;if(regime==="STRONG_TREND")score+=2;score+=advancedScore;score=Math.round(Math.min(95,Math.max(0,score)));
 return {ok:true,symbol:s.symbol,side:trend,entry,sl,tp,rr,score,quality:score>=84?"PREMIUM":"NORMAL",spreadPips:sp,rsi:rrsi,atrM5:a5,atrM15:a15,atrH1:a1h,atrH4:a4h,stopAtr:stopDist/Math.max(a5,1e-12),chaseAtr,trendStrength,h4Trend,h1Trend,m15Trend,quoteAgeSec:ageSec,regime,setup,family:pf.family,advancedEvidence:{score:advancedScore,tags:advancedTags,m5:pa5,m15:pa15,location:loc},thesis:`${trend} ${regime} ${setup}; H4+H1+M15 aligned; structural invalidation outside M15 swing; soft PA/liquidity evidence=${advancedTags.join("|")||"neutral"}`,timestamp:s.timestamp||Date.now()};
}
export function rankForexCandidates(env,snapshots=[]){return snapshots.map(s=>buildForexCandidate(env,s)).filter(x=>x.ok).sort((a,b)=>b.score-a.score||b.rr-a.rr);}