import {forexAutoConfig} from "./forex-auto-config.js";
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
export function evaluateThe5ersRules(env,s={}){
 const c=forexAutoConfig(env),r=c.rules,eq=n(s.equity),bal=n(s.balance),start=n(s.initialBalance,bal||eq),dayStart=n(s.dayStartBalance,start),openRiskPct=n(s.openRiskPct),dailyLossPct=dayStart>0?Math.max(0,(dayStart-eq)/dayStart*100):0,totalLossPct=start>0?Math.max(0,(start-eq)/start*100):0,margin=n(s.margin,-1),freeMargin=n(s.freeMargin,-1),marginLevelPct=n(s.marginLevelPct,-1),freeMarginPct=eq>0&&freeMargin>=0?freeMargin/eq*100:-1,usedMarginPct=eq>0&&margin>=0?margin/eq*100:-1;
 const reasons=[];
 if(!start||!eq)reasons.push("ACCOUNT_EQUITY_MISSING");
 if(dailyLossPct>=r.internalDailyStopPct)reasons.push("INTERNAL_DAILY_STOP");
 if(dailyLossPct>=r.maxDailyLossPct)reasons.push("THE5ERS_DAILY_LOSS_BREACH");
 if(totalLossPct>=r.maxTotalLossPct)reasons.push("THE5ERS_MAX_LOSS_BREACH");
 if(openRiskPct>=c.risk.maxTotalOpenRiskPct)reasons.push("TOTAL_OPEN_RISK_CAP");
 if(dailyLossPct+openRiskPct>=r.projectedDailyStopPct)reasons.push("PROJECTED_DAILY_STOP_CAP");
 if(n(s.lossStreak)>=c.risk.maxLossStreak)reasons.push("LOSS_STREAK_PAUSE");
 if(r.newsCalendarFailClosed&&s.newsCalendarOk===false)reasons.push("NEWS_CALENDAR_UNAVAILABLE");
 if(Boolean(s.newsBlocked))reasons.push("HIGH_IMPACT_NEWS_WINDOW");
 if(c.margin.requireBrokerMarginMetrics&&(margin<0||freeMargin<0||marginLevelPct<0))reasons.push("MARGIN_METRICS_MISSING");
 if(freeMarginPct>=0&&freeMarginPct<c.margin.minFreeMarginPctOfEquity)reasons.push("FREE_MARGIN_RESERVE_LOW");
 if(usedMarginPct>=0&&usedMarginPct>c.margin.maxUsedMarginPctOfEquity)reasons.push("USED_MARGIN_TOO_HIGH");
 if(marginLevelPct>=0&&margin>0&&marginLevelPct<c.margin.minMarginLevelPct)reasons.push("MARGIN_LEVEL_TOO_LOW");
 return {ok:reasons.length===0,reasons,metrics:{dailyLossPct,totalLossPct,openRiskPct,equity:eq,balance:bal,initialBalance:start,dayStartBalance:dayStart,margin,freeMargin,marginLevelPct,freeMarginPct,usedMarginPct,openPositions:n(s.openPositions)},limits:{daily:r.maxDailyLossPct,total:r.maxTotalLossPct,internalDaily:r.internalDailyStopPct,projectedDaily:r.projectedDailyStopPct,openRisk:c.risk.maxTotalOpenRiskPct,minFreeMarginPct:c.margin.minFreeMarginPctOfEquity,maxUsedMarginPct:c.margin.maxUsedMarginPctOfEquity,minMarginLevelPct:c.margin.minMarginLevelPct}};
}
export function sizeRiskPct(env,{quality="NORMAL",correlated=false,dailyLossPct=0}={}){
 const c=forexAutoConfig(env);let x=quality==="PREMIUM"?c.risk.premiumRiskPct:c.risk.normalRiskPct;if(correlated)x*=.55;if(dailyLossPct>.75)x*=.7;return Math.min(c.risk.hardMaxRiskPct,Math.max(.1,x));
}