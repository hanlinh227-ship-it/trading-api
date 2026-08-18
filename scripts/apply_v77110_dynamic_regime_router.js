const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing start '+label);const b=s.indexOf(end,a+start.length);if(b<0)throw new Error('Missing end '+label);s=s.slice(0,a)+repl+s.slice(b);}
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}

s=s.replaceAll('V77.10.2','V77.11.0');
s=s.replaceAll('Trading V77.11.0 Adaptive Entry Intelligence Hub','Trading V77.11.0 Dynamic Regime Entry Hub');

const routerBlock=`function allowedProfileModes(prior){
  const f=(prior?.families||[]).join('|').toUpperCase(),out=[];
  if(/MEANREV|REVERT|CONTRA|FADE|SLOW|SESSION/.test(f))out.push("MEAN_REVERSION");
  if(/BREADTH|RELATIVE|BTCALIGN|HYBRID|L2/.test(f))out.push("RELATIVE");
  if(/TREND|MOM|MOMENTUM|FAST|H1TREND|H4TREND|D1TREND|BTC_CORE|H1|H4|D1/.test(f))out.push("TREND");
  if(!out.length)out.push("GENERIC");return [...new Set(out)];
}
function sideFromTrendVotes(votes,H4,H1){if(votes.bull>=2)return "LONG";if(votes.bear>=2)return "SHORT";if(H4?.trend===H1?.trend&&H1?.trend!=="NEUTRAL")return H1.trend==="BULLISH"?"LONG":"SHORT";return "NEUTRAL";}
function regimeRouteScores(prior,T,context={}){
  const {M5,M15,H1,H4,D1}=T,v=directionalVotes(D1,H4,H1),allowed=allowedProfileModes(prior),baseSide=sideFromTrendVotes(v,H4,H1),r=Number(H1?.rsi14??50),m15r=Number(M15?.rsi14??50);
  const trendStrength=Math.max(v.bull,v.bear)/3,trendSide=baseSide,momOK=trendSide==="LONG"?(r>=52&&H1.close>=H1.ema20):(trendSide==="SHORT"?(r<=48&&H1.close<=H1.ema20):false),hAlign=H4?.trend===H1?.trend&&H1?.trend!=="NEUTRAL";
  const rel=Number(context.relativeStrength??context.strengthDiff),ctxMag=Number.isFinite(rel)?Math.min(1,Math.abs(rel)/2):0,ctxSide=Number.isFinite(rel)&&Math.abs(rel)>.05?(rel>0?"LONG":"SHORT"):"NEUTRAL";
  const hAtr=Number(H1?.atr14)||1,emaDist=Number.isFinite(H1?.ema20)?Math.abs(H1.close-H1.ema20)/hAtr:0,ext=Math.min(1,Math.max(Math.abs(r-50)/22,Math.abs(m15r-50)/24,Math.min(1,emaDist/2)));
  const longRev=H1?.bullishReclaim||M15?.bullishReclaim||M5?.bullishReclaim,shortRev=H1?.bearishReclaim||M15?.bearishReclaim||M5?.bearishReclaim;
  let mrSide="NEUTRAL";if(r<=43||m15r<=40||longRev)mrSide="LONG";if(r>=57||m15r>=60||shortRev)mrSide="SHORT";if(longRev&&!shortRev)mrSide="LONG";if(shortRev&&!longRev)mrSide="SHORT";
  const scores={};
  if(allowed.includes("TREND"))scores.TREND=Math.round(34+30*trendStrength+(momOK?15:0)+(hAlign?10:0)+6*sessionFit(prior));
  if(allowed.includes("RELATIVE")){const sideAgree=ctxSide!=="NEUTRAL"&&(trendSide===ctxSide||trendSide==="NEUTRAL");scores.RELATIVE=Math.round(34+30*ctxMag+(Number(context.score||0)>=7?10:0)+(sideAgree?12:0)+(hAlign?5:0));}
  if(allowed.includes("MEAN_REVERSION")){const revEvidence=mrSide==="LONG"?longRev:mrSide==="SHORT"?shortRev:false;scores.MEAN_REVERSION=Math.round(30+32*ext+(revEvidence?18:0)+(emaDist>=.75?8:0)+5*sessionFit(prior));}
  if(allowed.includes("GENERIC"))scores.GENERIC=Math.round(38+22*trendStrength+(hAlign?10:0)+10*ctxMag);
  const activeMode=Object.entries(scores).sort((a,b)=>b[1]-a[1])[0]?.[0]||allowed[0]||"GENERIC";
  let side=activeMode==="MEAN_REVERSION"?mrSide:activeMode==="RELATIVE"?(ctxSide!=="NEUTRAL"?ctxSide:trendSide):trendSide;
  if(activeMode==="RELATIVE"&&trendSide!=="NEUTRAL"&&ctxSide!=="NEUTRAL"&&trendSide!==ctxSide&&Math.abs(rel)<1)side=trendSide;
  let htfPass=false;
  if(activeMode==="TREND")htfPass=side!=="NEUTRAL"&&((side==="LONG"&&v.bull>=2)||(side==="SHORT"&&v.bear>=2)||hAlign);
  else if(activeMode==="RELATIVE")htfPass=side!=="NEUTRAL"&&ctxMag>=.18&&((side==="LONG"?v.bull:v.bear)>=1||Number(context.score||0)>=8);
  else if(activeMode==="MEAN_REVERSION")htfPass=side!=="NEUTRAL"&&ext>=.35&&(mrSide!=="NEUTRAL");
  else htfPass=side!=="NEUTRAL"&&(Math.max(v.bull,v.bear)>=2||hAlign);
  return {allowed,activeMode,scores,side,htfPass,votes:v,trendSide,ctxSide,ctxMag:Number(ctxMag.toFixed(3)),extension:Number(ext.toFixed(3)),emaDistATR:Number(emaDist.toFixed(3))};
}
function methodAssessment(symbol,type,T,context={}){
  const prior=v73Prior(symbol,type),route=regimeRouteScores(prior,T,context),mode=route.activeMode,{H1}=T;let fit=Number(route.scores[mode]||50),why=["dynamic regime: "+mode];
  if(type==="forex"&&Number.isFinite(context.strengthDiff))why.push("currency-strength context");
  if(type==="crypto"){if(Number.isFinite(context.relativeStrength))why.push("BTC-relative context");if(Number.isFinite(context.fundingRate)){if(Math.abs(context.fundingRate)>.0015)fit-=6;why.push("derivatives context");}}
  if(type==="metal"&&Number.isFinite(context.relativeStrength))why.push("metal-relative context");
  fit=Math.max(0,Math.min(100,Math.round(fit)));
  return {side:route.side,methodFit:fit,activeMode:mode,allowedModes:route.allowed,routeScores:route.scores,htfPass:route.htfPass,route,profile:prior.profile||prior.family||"GENERIC",families:prior.families||[],sessionFit:Math.round(sessionFit(prior)*100),why,drivers:prior.newsProfile?.profileDrivers||prior.newsProfile?.symbolSpecific||[]};
}
`;
replaceRange('function methodAssessment(','function setupScore(',routerBlock+'function setupScore(','dynamic method router');

replaceRange('function profileMode(','function sideTrendMatch(',`function profileMode(intel){return intel?.activeMode||intel?.allowedModes?.[0]||"GENERIC";}\nfunction sideTrendMatch(`,'profileMode active route');

// Replace deep HTF gate to honor the method-specific route instead of forcing 2/3 trend votes on every profile.
const old='const intel=methodAssessment(s,type,{M5,M15,H1,H4,D1},context),votes=directionalVotes(D1,H4,H1),side=intel.side,htf=side!=="NEUTRAL"&&((side==="LONG"&&votes.bull>=2)||(side==="SHORT"&&votes.bear>=2));';
const neu='const intel=methodAssessment(s,type,{M5,M15,H1,H4,D1},context),votes=intel.route?.votes||directionalVotes(D1,H4,H1),side=intel.side,htf=!!intel.htfPass;';
mustReplace(old,neu,'method-aware HTF gate');

// Enrich Watch/Hub persistence with current active mode/route scores.
mustReplace('method:x.method||null,context:x.context||null,updatedAt:Date.now(),engine:CONFIG.version','method:x.method||null,context:x.context||null,entryPolicy:x.entryPolicy||null,updatedAt:Date.now(),engine:CONFIG.version','persist entry policy');

// Show active route in individual/Hub UI when present.
s=s.replace('if(a.method?.profile)L.push(`Method: ${a.method.profile}`);','if(a.method?.profile)L.push(`Profile: ${a.method.profile}`);if(a.method?.activeMode)L.push(`Active route: ${a.method.activeMode}${a.method.allowedModes?.length>1?" (allowed: "+a.method.allowedModes.join("/")+")":""}`);');
s=s.replace('if(a.method?.profile||a.method?.families?.length)line+=`\\n   ↳ Method: ${a.method?.profile||a.method?.families?.[0]}`;','if(a.method?.profile||a.method?.families?.length)line+=`\\n   ↳ Profile: ${a.method?.profile||a.method?.families?.[0]}`;if(a.method?.activeMode)line+=`\\n   ↳ Route: ${a.method.activeMode}`;');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.11.0 dynamic regime router');
