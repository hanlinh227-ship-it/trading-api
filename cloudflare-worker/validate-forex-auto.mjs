import assert from "node:assert/strict";
import {forexAutoConfig,FOREX_AUTO_VERSION} from "./forex-auto-config.js";
import {evaluateThe5ersRules} from "./forex-the5ers-rule-engine.js";
import {buildForexCandidate} from "./forex-signal-engine.js";
import {recordForexEntry,recordForexOutcome,getForexLearningContext} from "./forex-learning-engine.js";

const mkBars=(start,step,count,noise=.00025,seconds=300)=>Array.from({length:count},(_,i)=>{const close=start+step*i+(i%3-1)*noise,open=close-step*.35;return {time:1700000000+i*seconds,open,high:Math.max(open,close)+noise,low:Math.min(open,close)-noise,close,volume:100+i};});
const env={};
const cfg=forexAutoConfig(env);
assert.equal(FOREX_AUTO_VERSION,"FOREX-AUTO-0.4.1-PAPER");
assert.equal(cfg.branchId,"FOREX_THE5ERS_INDEPENDENT");
assert.equal(cfg.rules.internalDailyStopPct,4);
assert.equal(cfg.rules.projectedDailyStopPct,4);
assert.equal(cfg.rules.alternateTradeSide,true);
assert.equal(cfg.rules.alternationScope,"ACCOUNT_FILLED_ENTRY_SEQUENCE");
assert.equal(cfg.rules.alternationNoForceEntry,true);
assert.equal(cfg.risk.hardMaxRiskPct,1);
assert.equal(forexAutoConfig({FOREX_NORMAL_RISK_PCT:"1",FOREX_PREMIUM_RISK_PCT:"1"}).risk.hardMaxRiskPct,1);
assert.equal(forexAutoConfig({FOREX_NORMAL_RISK_PCT:"1.5",FOREX_PREMIUM_RISK_PCT:"2"}).risk.normalRiskPct,1);
assert.equal(forexAutoConfig({FOREX_NORMAL_RISK_PCT:"1.5",FOREX_PREMIUM_RISK_PCT:"2"}).risk.premiumRiskPct,1);
assert.equal(cfg.execution.liveEnabled,false);
assert.equal(forexAutoConfig({FOREX_AUTO_LIVE:"true"}).execution.liveEnabled,false,"LIVE must remain disabled without target config");
assert.equal(forexAutoConfig({FOREX_AUTO_LIVE:"true",FOREX_TARGET_PCT:"8"}).execution.liveEnabled,true);

let r=evaluateThe5ersRules(env,{balance:100000,equity:95900,initialBalance:100000,dayStartBalance:100000,openRiskPct:0,openPositions:0,newsCalendarOk:true});
assert.equal(r.ok,false);assert(r.reasons.includes("INTERNAL_DAILY_STOP"));
r=evaluateThe5ersRules(env,{balance:100000,equity:97000,initialBalance:100000,dayStartBalance:100000,openRiskPct:.5,openPositions:1,newsCalendarOk:true});
assert.equal(r.ok,true);
r=evaluateThe5ersRules(env,{balance:100000,equity:100000,initialBalance:100000,dayStartBalance:100000,openRiskPct:0,openPositions:0,newsCalendarOk:false});
assert.equal(r.ok,false);assert(r.reasons.includes("NEWS_CALENDAR_UNAVAILABLE"));

const h4=mkBars(1.04,.0014,70,.00045,14400),h1=mkBars(1.08,.00045,70,.00018,3600),m15=mkBars(1.095,.00016,55,.00012,900),m5=mkBars(1.101,.00005,55,.00010,300),last=m5.at(-1).close;
const normal=buildForexCandidate(env,{symbol:"EURUSD",bid:last-.00004,ask:last+.00004,last,timestamp:Math.floor(Date.now()/1000),bars:{M5:m5,M15:m15,H1:h1,H4:h4}});
assert(normal && typeof normal.ok==="boolean");
if(normal.ok){assert(["TREND_PULLBACK","RETEST_CONTINUATION","LATE_RETEST"].includes(normal.setup));assert(normal.family==="STABLE_MAJOR");assert(normal.rr>=1.5);assert(normal.chaseAtr<=cfg.risk.maxChaseAtr);assert.equal(normal.h4Trend,normal.side);}
const stale=buildForexCandidate(env,{symbol:"EURUSD",bid:last-.00004,ask:last+.00004,last,timestamp:Math.floor(Date.now()/1000)-300,bars:{M5:m5,M15:m15,H1:h1,H4:h4}});
assert.equal(stale.ok,false);assert.equal(stale.reason,"STALE_QUOTE");
const far=buildForexCandidate(env,{symbol:"EURUSD",bid:last+.005,ask:last+.0051,last:last+.005,timestamp:Math.floor(Date.now()/1000),bars:{M5:m5,M15:m15,H1:h1,H4:h4}});
assert.equal(far.ok,false);assert(["PRICE_TOO_EXTENDED_WAIT_RETEST","NO_HEALTHY_PULLBACK","STOP_TOO_WIDE","STRUCTURE_RR_TOO_LOW","NO_H4_H1_M15_ALIGNMENT"].includes(far.reason));

class KV{constructor(){this.m=new Map()}async get(k,o){const v=this.m.get(k);if(v==null)return null;return o?.type==="json"?JSON.parse(v):v}async put(k,v){this.m.set(k,v)}}
const TRADING_STATE=new KV(),lenv={TRADING_STATE};
for(let i=1;i<=12;i++){await recordForexEntry(lenv,"T1",{ticket:i,symbol:"EURUSD",side:i%2?"BUY":"SELL",riskUsd:100,setup:"TREND_PULLBACK",regime:"TREND"});await recordForexOutcome(lenv,"T1",{ticket:i,pnl:i<=10?-60:10,mfeR:.4,maeR:.7,exitReason:"TEST"});}
const lc=await getForexLearningContext(lenv,"T1",{symbol:"EURUSD"});
assert.equal(lc.active,true);assert.equal(lc.degraded,true);assert(lc.riskMultiplier<=.7);assert(lc.scoreDelta<=-3);

console.log(JSON.stringify({ok:true,version:FOREX_AUTO_VERSION,checks:{dailyStop4:true,liveTargetLock:true,h4Freshness:true,newsFailClosed:true,qualityOnlySideAlternation:true,noForcedOppositeEntry:true,maxRiskPerTrade1Pct:true,boundedLearning:true}},null,2));