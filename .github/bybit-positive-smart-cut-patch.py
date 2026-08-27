from pathlib import Path
import re

p=Path('cloudflare-worker/bybit-position-manager.js')
s=p.read_text()
new_func='''function smartCutAssessment({env,cfg,r,ageSec,momentum,plan}){
  const enabled=envBool(env.BYBIT_DISCRETIONARY_CUT_ENABLED,cfg?.risk?.smartCutEnabled===true);if(!enabled||!momentum.available)return {enabled,eligible:false,score:0,reason:"SMART_CUT_DISABLED_OR_NO_DATA"};
  const minAge=Math.max(180,Number(env.BYBIT_CUT_MIN_AGE_SEC||cfg?.risk?.smartCutMinAgeSec||180)),thresholdR=dynamicCutThresholdR(ageSec,env),scoreNeed=Math.max(6,Math.min(9,Number(env.BYBIT_SMART_CUT_SCORE||cfg?.risk?.smartCutScore||7))),positiveEnabled=envBool(env.BYBIT_POSITIVE_SMART_CUT_ENABLED,cfg?.risk?.smartCutPositiveEnabled!==false),positiveMinAge=Math.max(120,Number(env.BYBIT_POSITIVE_CUT_MIN_AGE_SEC||cfg?.risk?.smartCutPositiveMinAgeSec||180)),positiveMinR=clamp(Number(env.BYBIT_POSITIVE_CUT_MIN_R||cfg?.risk?.smartCutPositiveMinR||.05),.01,.50),positiveMinPeakR=clamp(Number(env.BYBIT_POSITIVE_CUT_MIN_PEAK_R||cfg?.risk?.smartCutPositiveMinPeakR||.30),.15,1.20),positiveGivebackR=clamp(Number(env.BYBIT_POSITIVE_CUT_GIVEBACK_R||cfg?.risk?.smartCutPositiveGivebackR||.25),.10,.80),peakR=Math.max(Number(plan?.peakR||0),r),givebackR=Math.max(0,peakR-r);let score=0;const signals=[];const add=(pts,name,ok)=>{if(ok){score+=pts;signals.push(name);}};
  add(2,"LOSS_DEPTH",r<=thresholdR);add(1,"DEEP_LOSS",r<=thresholdR-.12);add(2,"ADVERSE_TREND",momentum.adverseTrend);add(1,"ADVERSE_BARS_3",momentum.adverseBars>=3);add(1,"ADVERSE_BARS_4",momentum.adverseBars>=4);add(2,"MOMENTUM_BREAK",momentum.momentumR<=-.18);add(1,"FAST_SLOPE_BREAK",momentum.fastSlopeR<=-.08);add(1,"SLOW_SLOPE_BREAK",momentum.slowSlopeR<=-.04);add(2,"STRUCTURE_BREAK",momentum.structureBroken);add(1,"ADVERSE_BODY_EXPANSION",momentum.adverseBodyR>=.35);add(1,"VOLUME_CONFIRM",momentum.volumeRatio>=1.20);add(1,"RANGE_EXPANSION",momentum.rangeExpansion>=1.25);add(2,"PROFIT_GIVEBACK",positiveEnabled&&r>=positiveMinR&&peakR>=positiveMinPeakR&&givebackR>=positiveGivebackR);add(1,"POSITIVE_THESIS_BREAK",positiveEnabled&&r>0&&momentum.adverseTrend&&(momentum.structureBroken||momentum.adverseBars>=3));
  const lossGate=ageSec>=minAge&&r<=thresholdR&&momentum.adverseTrend&&momentum.momentumR<=-.12&&(momentum.structureBroken||momentum.adverseBars>=3),positiveGate=positiveEnabled&&ageSec>=positiveMinAge&&r>=positiveMinR&&peakR>=positiveMinPeakR&&givebackR>=positiveGivebackR&&momentum.adverseTrend&&momentum.momentumR<=-.08&&(momentum.structureBroken||momentum.adverseBars>=3),emergency=ageSec>=minAge&&r<=-.88&&momentum.adverseTrend&&momentum.momentumR<=-.28&&(momentum.structureBroken||momentum.adverseBars>=4)&&score>=scoreNeed,candidate=(lossGate||positiveGate)&&score>=scoreNeed,previous=Number(plan?.smartCutCandidateCount||0),confirmations=candidate?previous+1:0,required=Math.max(2,Math.min(3,Number(env.BYBIT_SMART_CUT_CONFIRMATIONS||cfg?.risk?.smartCutConfirmations||2))),mode=positiveGate?"POSITIVE_THESIS_INVALIDATION":lossGate?"LOSS_THESIS_INVALIDATION":"NONE";
  return {enabled,eligible:emergency||(candidate&&confirmations>=required),candidate,emergency,mode,score,scoreNeed,signals,thresholdR,minAge,positiveEnabled,positiveMinAge,positiveMinR,positiveMinPeakR,positiveGivebackR,peakR,givebackR,confirmations,required};
}'''
s2,n=re.subn(r'function smartCutAssessment\(\{env,cfg,r,ageSec,momentum,plan\}\)\{.*?\n\}\nfunction pendingCut',new_func+'\nfunction pendingCut',s,flags=re.S)
if n!=1: raise SystemExit(f'smartCutAssessment replacement count={n}')
old='cutReason=cut.emergency?"SMART_CUT_EMERGENCY_INVALIDATION":"SMART_CUT_CONFIRMED_INVALIDATION";'
new='cutReason=cut.emergency?"SMART_CUT_EMERGENCY_INVALIDATION":cut.mode==="POSITIVE_THESIS_INVALIDATION"?"SMART_CUT_POSITIVE_THESIS_INVALIDATION":"SMART_CUT_CONFIRMED_INVALIDATION";'
if old not in s2: raise SystemExit('cutReason marker missing')
p.write_text(s2.replace(old,new,1))

c=Path('cloudflare-worker/bybit-auto-config.js')
x=c.read_text()
marker='    smartCutEnabled:true,\n    smartCutMinAgeSec:180,'
repl='    smartCutEnabled:true,\n    smartCutPositiveEnabled:true,\n    smartCutPositiveMinAgeSec:180,\n    smartCutPositiveMinR:.05,\n    smartCutPositiveMinPeakR:.30,\n    smartCutPositiveGivebackR:.25,\n    smartCutMinAgeSec:180,'
if marker not in x: raise SystemExit('config marker missing')
x=x.replace(marker,repl,1)
marker2='  c.risk.smartCutEnabled=String(env.BYBIT_DISCRETIONARY_CUT_ENABLED??String(c.risk.smartCutEnabled)).toLowerCase()==="true";\n  c.risk.smartCutMinAgeSec='
repl2='  c.risk.smartCutEnabled=String(env.BYBIT_DISCRETIONARY_CUT_ENABLED??String(c.risk.smartCutEnabled)).toLowerCase()==="true";\n  c.risk.smartCutPositiveEnabled=String(env.BYBIT_POSITIVE_SMART_CUT_ENABLED??String(c.risk.smartCutPositiveEnabled)).toLowerCase()==="true";\n  c.risk.smartCutPositiveMinAgeSec=Math.max(120,Math.min(900,Math.round(n(env,"BYBIT_POSITIVE_CUT_MIN_AGE_SEC",c.risk.smartCutPositiveMinAgeSec))));\n  c.risk.smartCutPositiveMinR=Math.max(.01,Math.min(.50,n(env,"BYBIT_POSITIVE_CUT_MIN_R",c.risk.smartCutPositiveMinR)));\n  c.risk.smartCutPositiveMinPeakR=Math.max(.15,Math.min(1.20,n(env,"BYBIT_POSITIVE_CUT_MIN_PEAK_R",c.risk.smartCutPositiveMinPeakR)));\n  c.risk.smartCutPositiveGivebackR=Math.max(.10,Math.min(.80,n(env,"BYBIT_POSITIVE_CUT_GIVEBACK_R",c.risk.smartCutPositiveGivebackR)));\n  c.risk.smartCutMinAgeSec='
if marker2 not in x: raise SystemExit('config runtime marker missing')
c.write_text(x.replace(marker2,repl2,1))
