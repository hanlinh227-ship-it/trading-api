import {forexAutoConfig} from "./forex-auto-config.js";
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
export function evaluateThe5ersRules(env,s={}){
 const c=forexAutoConfig(env),r=c.rules,eq=n(s.equity),bal=n(s.balance),start=n(s.initialBalance,bal||eq),dayStart=n(s.dayStartBalance,start),openRiskPct=n(s.openRiskPct),dailyLossPct=dayStart>0?Math.max(0,(dayStart-eq)/dayStart*100):0,totalLossPct=start>0?Math.max(0,(start-eq)/start*100):0;
 const reasons=[];
 if(!start||!eq)reasons.push("ACCOUNT_EQUITY_MISSING");
 if(dailyLossPct>=r.internalDailyStopPct)reasons.push("INTERNAL_DAILY_STOP");
 if(dailyLossPct>=r.maxDailyLossPct)reasons.push("THE5ERS_DAILY_LOSS_BREACH");
 if(totalLossPct>=r.maxTotalLossPct)reasons.push("THE5ERS_MAX_LOSS_BREACH");
 if(openRiskPct>=c.risk.maxTotalOpenRiskPct)reasons.push("TOTAL_OPEN_RISK_CAP");
 if(n(s.lossStreak)>=c.risk.maxLossStreak)reasons.push("LOSS_STREAK_PAUSE");
 if(Boolean(s.newsBlocked))reasons.push("HIGH_IMPACT_NEWS_WINDOW");
 if(n(s.openPositions)>=c.maxOpenPositions)reasons.push("MAX_OPEN_POSITIONS");
 return {ok:reasons.length===0,reasons,metrics:{dailyLossPct,totalLossPct,openRiskPct,equity:eq,balance:bal,initialBalance:start,dayStartBalance:dayStart},limits:{daily:r.maxDailyLossPct,total:r.maxTotalLossPct,internalDaily:r.internalDailyStopPct,openRisk:c.risk.maxTotalOpenRiskPct}};
}
export function sizeRiskPct(env,{quality="NORMAL",correlated=false,dailyLossPct=0}={}){
 const c=forexAutoConfig(env);let x=quality==="PREMIUM"?c.risk.premiumRiskPct:c.risk.normalRiskPct;if(correlated)x*=.55;if(dailyLossPct>.75)x*=.7;return Math.min(c.risk.hardMaxRiskPct,Math.max(.1,x));
}
