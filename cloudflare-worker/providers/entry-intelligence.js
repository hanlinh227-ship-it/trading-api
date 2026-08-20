// V78-027 — SIGNAL ENTRY INTELLIGENCE
// Conservative intelligence layer over already-finalized Signal decisions.
// It may adjust advisory Signal ranking and new-book admission only.
// It never fetches providers, changes decision thresholds, grants execution authority,
// places orders, or fabricates missing evidence.

const KEY="v78016:entry_intelligence:signal";
const CAP=240;
const TTL_SEC=21600;

const finite=v=>Number.isFinite(Number(v))?Number(v):null;
const text=v=>v==null||v===""?null:String(v);
const first=(...xs)=>xs.find(x=>x!=null&&x!=="")??null;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

function marketOf(a){
  const m=String(a?.market||"").toLowerCase();
  if(["forex","crypto","metal","index"].includes(m))return m;
  const s=String(a?.symbol||"").toUpperCase();
  if(/USDT$/.test(s))return "crypto";
  if(["XAUUSD","XAGUSD"].includes(s))return "metal";
  if(["NAS100","US30","US500","DEX","JP225"].includes(s))return "index";
  if(/^[A-Z]{6}$/.test(s))return "forex";
  return "unknown";
}

function quoteView(a){
  const q=a?.analysisQuote||a?.quote||null;
  if(!q)return {present:false,freshness:"MISSING",source:null,ageSec:null,price:null};
  return {present:true,freshness:q.fresh===true?"LIVE":q.fresh===false?"STALE":"UNKNOWN",source:text(q.source),ageSec:finite(q.quoteAgeSec),price:finite(first(q.price,a?.currentPrice,a?.entry))};
}

function plannedView(a){
  const p=a?.planned||a||{};
  return {entry:finite(first(p.entry,a?.entry)),sl:finite(first(p.sl,a?.sl)),tp:finite(first(p.tp2,p.tp1,p.tp,a?.tp2,a?.tp1,a?.tp)),rr:finite(first(p.targetRR,a?.targetRR,a?.rr))};
}

function existingRegime(a){return first(a?.regime?.name,a?.regime,a?.method?.activeMode,a?.method?.family,a?.method?.profile,a?.canonical?.regime);}
function existingSession(a){return first(a?.session?.name,a?.session,a?.canonical?.session,a?.context?.session);}
function existingLocation(a){return first(a?.location?.label,a?.location,a?.entryPolicy?.location,a?.canonical?.location,a?.reason==="M15_LOCATION_REQUIRED"?"M15_LOCATION_REQUIRED":null);}
function existingTrigger(a){return first(a?.trigger?.label,a?.trigger,a?.entryPolicy?.trigger,a?.canonical?.trigger,a?.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED"?"M5_MSS_DISPLACEMENT_RETEST_REQUIRED":null);}

function marketSpecific(a,market){
  const c=a?.context||{},micro=c?.microstructure||{},canon=a?.canonical||{};
  if(market==="forex")return {
    session:first(existingSession(a),c?.forexSession),
    currencyStrength:first(c?.currencyStrength,a?.currencyStrength,canon?.currencyStrength,c?.strengthDiff,a?.strengthDiff),
    crossPairConfirmation:first(c?.crossPairConfirmation,c?.relativeStrength,a?.relativeStrength),
    eventSensitivity:first(canon?.news?.source,c?.news?.source)
  };
  if(market==="crypto")return {
    funding:first(micro?.funding,micro?.fundingRate,c?.funding,c?.fundingRate,a?.funding,a?.fundingRate),
    openInterest:first(micro?.openInterest,micro?.oi,c?.openInterest,a?.openInterest),
    longShort:first(micro?.longShort,c?.longShort,a?.longShort),
    orderbook:first(micro?.orderbook,c?.orderbook,a?.orderbook),
    spread:first(micro?.spread,c?.spread,a?.spread),
    spotPerpIdentity:first(c?.instrumentIdentity,a?.instrumentType,a?.marketType)
  };
  if(market==="metal")return {
    session:first(existingSession(a),c?.metalSession),
    usdContext:first(c?.usdContext,c?.dxy,canon?.usdContext),
    ratesContext:first(c?.ratesContext,c?.yields,canon?.ratesContext),
    volatilityContext:first(c?.volatilityRegime,a?.volatilityRegime)
  };
  if(market==="index")return {
    session:first(existingSession(a),c?.indexSession),
    instrumentIdentity:first(c?.instrumentIdentity,a?.instrumentType),
    crossIndexConfirmation:first(c?.crossIndexConfirmation,c?.relativeStrength,a?.relativeStrength),
    riskContext:first(c?.riskSentiment,canon?.riskSentiment)
  };
  return {};
}

function completeness(obj){const vals=Object.values(obj||{}),known=vals.filter(v=>v!=null&&v!=="UNKNOWN"&&v!=="MISSING").length;return {known,total:vals.length,ratio:vals.length?Number((known/vals.length).toFixed(3)):0};}
function actionable(a){return ["MARKET","LIMIT","MARKET_SIGNAL","MARKET_PLAN","LIMIT_PLAN"].includes(String(a?.status||""))||["MARKET","LIMIT","INDICATIVE_LIMIT"].includes(String(a?.planned?.mode||""));}
function statusActionable(a){return ["MARKET","LIMIT","MARKET_SIGNAL","MARKET_PLAN","LIMIT_PLAN"].includes(String(a?.status||""));}

function qualityView({q,p,coreComp,specificComp,hardBlocks,a}){
  let score=50;
  if(q.freshness==="LIVE")score+=15;else if(q.freshness==="STALE")score-=35;else if(q.freshness==="MISSING")score-=25;else score-=8;
  score+=Math.round((coreComp.ratio-.5)*30);
  score+=Math.round((specificComp.ratio-.5)*14);
  if(p.entry!=null&&p.sl!=null&&p.tp!=null)score+=10;
  if(p.rr!=null)score+=clamp(Math.round((p.rr-1)*6),-8,12);
  score-=Math.min(30,hardBlocks.length*12);
  if(a?.contextOnly)score-=20;
  score=clamp(score,0,100);
  return {score,grade:score>=85?"A":score>=72?"B":score>=58?"C":score>=42?"D":"E"};
}

function whyNowText({market,session,regime,a}){
  const xs=[market&&market!=="unknown"?market.toUpperCase():null,session,regime,a?.reason||a?.status].filter(Boolean);
  return xs.length?xs.join(" • "):"UNKNOWN";
}

export function buildEntryIntelligenceShadow(a,{runtimeVersion=null,scanId=null}={}){
  if(!a?.symbol)return null;
  const market=marketOf(a),q=quoteView(a),p=plannedView(a),regime=existingRegime(a),session=existingSession(a),location=existingLocation(a),trigger=existingTrigger(a),specific=marketSpecific(a,market),now=Date.now();
  const hardBlocks=[];
  if(a?.status==="DATA_BLOCK")hardBlocks.push(a?.reason||a?.error||"DATA_BLOCK");
  if(!statusActionable(a)&&a?.reason==="M15_LOCATION_REQUIRED")hardBlocks.push("M15_LOCATION_REQUIRED");
  if(!statusActionable(a)&&a?.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")hardBlocks.push("M5_MSS_DISPLACEMENT_RETEST_REQUIRED");
  if(!statusActionable(a)&&a?.reason==="RR_QUALITY_REQUIRED")hardBlocks.push("RR_QUALITY_REQUIRED");
  if(q.freshness==="STALE")hardBlocks.push("QUOTE_STALE");
  if(q.freshness==="MISSING")hardBlocks.push("QUOTE_MISSING");
  if(actionable(a)&&p.entry==null)hardBlocks.push("ENTRY_MISSING");
  if(actionable(a)&&p.sl==null)hardBlocks.push("SL_MISSING");
  if(actionable(a)&&p.tp==null&&p.rr==null)hardBlocks.push("TARGET_MISSING");

  const reasoning={
    whyNow:whyNowText({market,session,regime,a}),
    whyPrice:p.entry!=null?`Planned entry ${p.entry}`:(q.price!=null?`Current analysis reference ${q.price}`:"MISSING_ENTRY_EVIDENCE"),
    whySl:p.sl!=null?`Structural invalidation / planned SL ${p.sl}`:"MISSING_SL_EVIDENCE",
    whyTp:p.tp!=null?`Planned target ${p.tp}${p.rr!=null?` • RR ${p.rr}`:""}`:(p.rr!=null?`Planned RR ${p.rr}`:"MISSING_TP_RR_EVIDENCE"),
    invalidates:p.sl!=null?`Setup invalid below/above structural SL ${p.sl}`:first(a?.reason,"UNKNOWN")
  };
  const core={regime,session,location,trigger,quoteFreshness:q.freshness,rr:p.rr,entry:p.entry,sl:p.sl,tp:p.tp},coreComp=completeness(core),specificComp=completeness(specific),quality=qualityView({q,p,coreComp,specificComp,hardBlocks,a});
  const promotionAllowed=!hardBlocks.some(x=>["QUOTE_STALE","QUOTE_MISSING","ENTRY_MISSING","SL_MISSING","TARGET_MISSING","DATA_BLOCK","M15_LOCATION_REQUIRED","M5_MSS_DISPLACEMENT_RETEST_REQUIRED","RR_QUALITY_REQUIRED"].includes(String(x)))&&!a?.contextOnly;
  return {revision:"V78-027",createdAt:now,symbol:a.symbol,market,side:a.side||null,existingDecision:{status:a.status||"UNKNOWN",reason:a.reason||null,score:finite(a.score)},quote:q,plan:p,structure:{regime,session,location,trigger},marketSpecific:specific,reasoning,quality,promotion:{allowed:promotionAllowed,mode:"ADVISORY_SIGNAL_ONLY",reasons:promotionAllowed?["NO_HARD_EVIDENCE_BLOCK"]:[...new Set(hardBlocks)]},integrity:{core:coreComp,marketSpecific:specificComp,missingCore:Object.entries(core).filter(([,v])=>v==null||v==="UNKNOWN"||v==="MISSING").map(([k])=>k),hardBlocks:[...new Set(hardBlocks)]},authority:{shadowOnly:false,changesDecision:false,changesRanking:true,changesBookAdmission:true,executionAuthority:"NONE"},lineage:{runtimeVersion,scanId,sourceStatus:a.status||null}};
}

export function entryIntelligenceRankAdjustment(a){
  const x=buildEntryIntelligenceShadow(a);if(!x)return 0;
  let adj=0;
  adj+=Math.round((x.integrity?.core?.ratio||0)*24);
  adj+=Math.round((x.integrity?.marketSpecific?.ratio||0)*10);
  if(x.quote?.freshness==="LIVE")adj+=12;
  if(x.quote?.freshness==="STALE")adj-=120;
  if(x.quote?.freshness==="MISSING")adj-=100;
  if(x.promotion?.allowed===false)adj-=90;
  if(x.quality?.grade==="A")adj+=18;else if(x.quality?.grade==="B")adj+=10;else if(x.quality?.grade==="D")adj-=18;else if(x.quality?.grade==="E")adj-=35;
  return clamp(adj,-180,64);
}

export function entryIntelligencePromotionAllowed(a){const x=buildEntryIntelligenceShadow(a);return x?.promotion?.allowed!==false;}

async function append(env,row){if(!env?.TRADING_STATE||!row)return;try{const old=await env.TRADING_STATE.get(KEY,"json"),rows=Array.isArray(old?.rows)?old.rows:[];rows.unshift(row);await env.TRADING_STATE.put(KEY,JSON.stringify({rows:rows.slice(0,CAP),updatedAt:Date.now()}),{expirationTtl:TTL_SEC});}catch{}}
export async function recordEntryIntelligenceShadow(env,row){await append(env,row);}
export async function getEntryIntelligenceShadow(env,limit=20){try{const v=await env.TRADING_STATE?.get(KEY,"json");return (Array.isArray(v?.rows)?v.rows:[]).slice(0,limit);}catch{return [];}}
