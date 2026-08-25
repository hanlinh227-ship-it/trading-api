import assert from "node:assert/strict";
import {forexAutoConfig,FOREX_AUTO_VERSION} from "./forex-auto-config.js";
import {evaluateThe5ersRules} from "./forex-the5ers-rule-engine.js";
import {buildForexCandidate} from "./forex-signal-engine.js";
import {recordForexEntry,recordForexOutcome,getForexLearningContext} from "./forex-learning-engine.js";

const mkBars=(start,step,count,noise=.00025)=>Array.from({length:count},(_,i)=>{const close=start+step*i+(i%3-1)*noise,open=close-step*.35;return {time:1700000000+i*300,open,high:Math.max(open,close)+noise,low:Math.min(open,close)-noise,close,volume:100+i};});
const env={};
const cfg=forexAutoConfig(env);
assert.equal(FOREX_AUTO_VERSION,"FOREX-AUTO-0.3.0-PAPER");
assert.equal(cfg.rules.internalDailyStopPct,4);
assert.equal(cfg.rules.projectedDailyStopPct,4);
assert.equal(cfg.execution.liveEnabled,false);
assert.equal(forexAutoConfig({FOREX_AUTO_LIVE:"true"}).execution.liveEnabled,false,"LIVE must remain disabled without target config");
assert.equal(forexAutoConfig({FOREX_AUTO_LIVE:"true",FOREX_TARGET_PCT:"8"}).execution.liveEnabled,true);

let r=evaluateThe5ersRules(env,{balance:100000,equity:95900,initialBalance:100000,dayStartBalance:100000,openRiskPct:0,openPositions:0});
assert.equal(r.ok,false);assert(r.reasons.includes("INTERNAL_DAILY_STOP"));
r=evaluateThe5ersRules(env,{balance:100000,equity:97000,initialBalance:100000,dayStartBalance:100000,openRiskPct:.5,openPositions:1});
assert.equal(r.ok,true);

const h1=mkBars(1.08,.00045,70,.00018),m15=mkBars(1.095,.00016,55,.00012),m5=mkBars(1.101,.00005,55,.00010),last=m5.at(-1).close;
const normal=buildForexCandidate(env,{symbol:"EURUSD",bid:last-.00004,ask:last+.00004,last,timestamp:Date.now(),bars:{M5:m5,M15:m15,H1:h1}});
assert(normal && typeof normal.ok==="boolean");
if(normal.ok){assert(["TREND_PULLBACK","RETEST_CONTINUATION","LATE_RETEST"].includes(normal.setup));assert(normal.family==="STABLE_MAJOR");assert(normal.rr>=1.5);assert(normal.chaseAtr<=cfg.risk.maxChaseAtr);}
const far=buildForexCandidate(env,{symbol:"EURUSD",bid:last+.005,ask:last+.0051,last:last+.005,timestamp:Date.now(),bars:{M5:m5,M15:m15,H1:h1}});
assert.equal(far.ok,false);assert(["PRICE_TOO_EXTENDED_WAIT_RETEST","NO_HEALTHY_PULLBACK","STOP_TOO_WIDE","STRUCTURE_RR_TOO_LOW"].includes(far.reason));

class KV{constructor(){this.m=new Map()}async get(k,o){const v=this.m.get(k);if(v==null)return null;return o?.type==="json"?JSON.parse(v):v}async put(k,v){this.m.set(k,v)}}
const TRADING_STATE=new KV(),lenv={TRADING_STATE};
for(let i=1;i<=12;i++){await recordForexEntry(lenv,"T1",{ticket:i,symbol:"EURUSD",side:i%2?"BUY":"SELL",riskUsd:100,setup:"TREND_PULLBACK",regime:"TREND"});await recordForexOutcome(lenv,"T1",{ticket:i,pnl:i<=8?-60:20,mfeR:.4,maeR:.7,exitReason:"TEST"});}
const lc=await getForexLearningContext(lenv,"T1",{symbol:"EURUSD"});
assert.equal(lc.active,true);assert.equal(lc.degraded,true);assert(lc.riskMultiplier<=.7);assert(lc.scoreDelta<=-3);

console.log(JSON.stringify({ok:true,version:FOREX_AUTO_VERSION,checks:{dailyStop4:true,liveTargetLock:true,signalGuards:true,boundedLearning:true}},null,2));
