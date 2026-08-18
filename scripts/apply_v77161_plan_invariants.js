const fs=require('fs');
const p='cloudflare-worker/index.js';let s=fs.readFileSync(p,'utf8');
function must(a,b,l){if(!s.includes(a))throw new Error('Missing '+l);s=s.replace(a,b);}
if(!s.includes('version: "V77.16.0"'))throw new Error('Expected V77.16.0');
s=s.replaceAll('V77.16.0','V77.16.1');
s=s.replace('Trading V77.16.1 Quality-Action Router Hub','Trading V77.16.1 Plan-Invariant Quality Hub');
const old='function planSignal(symbol,type,side,reason,planned,extra={}){const status=plannedModeLabel(planned);return {ok:true,status,action:status,symbol,market:type,side,reason,canonicalStage:reason,planned:{...planned,planType:status,executionVerified:false},executionReady:false,engine:CONFIG.version,...extra};}';
const neu='function planSignal(symbol,type,side,reason,planned,extra={}){const intel=extra?.method||null,q=rrQuality(planned,intel);if(planned&&Number.isFinite(Number(planned.targetRR))&&!q.pass)return watch(symbol,type,side,"RR_QUALITY_REQUIRED",{...extra,rejectedPlan:{entry:planned.entry,sl:planned.sl,tp1:planned.tp1,tp2:planned.tp2,targetRR:planned.targetRR,minQualityRR:q.minRR,entryStyle:planned.entryStyle||null},planned:null});const status=plannedModeLabel(planned);return {ok:true,status,action:status,symbol,market:type,side,reason,canonicalStage:reason,planned:{...planned,minQualityRR:planned?.minQualityRR??q.minRR,rrQualityPass:true,planType:status,executionVerified:false},executionReady:false,engine:CONFIG.version,...extra};}';
must(old,neu,'central plan RR invariant');
const oldInd='function indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior){';
const newInd='function indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior,intel=null){';
must(oldInd,newInd,'indicative intel signature');
must('  const p=buildTradePlan(side,e,M5,M15,H1,H4,D1,true,prior);if(!p||p.invalid)return null;const g=limitGeometry(side,M15.close,e,M5,M15,p);if(!g.pass)return null;\n  return {entry:p.entry,sl:p.sl,tp1:p.tp1,tp2:p.tp2,targetRR:p.targetRR,tp1RR:p.tp1RR,tp2RR:p.tp2RR,roomR:p.roomR,mode:"INDICATIVE_LIMIT",targetSource:p.targetSource,indicative:true,currentPrice:M15.close,geometry:g,entryStyle:"STRUCTURAL_PULLBACK_ZONE"};','  const p=buildTradePlan(side,e,M5,M15,H1,H4,D1,true,prior);if(!p||p.invalid)return null;const g=limitGeometry(side,M15.close,e,M5,M15,p),q=rrQuality(p,intel);if(!g.pass||!q.pass)return null;\n  return {entry:p.entry,sl:p.sl,tp1:p.tp1,tp2:p.tp2,targetRR:p.targetRR,tp1RR:p.tp1RR,tp2RR:p.tp2RR,roomR:p.roomR,mode:"INDICATIVE_LIMIT",targetSource:p.targetSource,indicative:true,currentPrice:M15.close,geometry:g,entryStyle:"STRUCTURAL_PULLBACK_ZONE",minQualityRR:q.minRR,rrQualityPass:true};','indicative RR invariant');
s=s.replaceAll('indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior)||','indicativePlan(side,M5,M15,H1,H4,D1,locPolicy,prior,intel)||');
fs.writeFileSync(p,s);console.log('Applied V77.16.1 plan invariants');
