// V78-016 — ENTRY INTELLIGENCE FOUNDATION (SHADOW ONLY)
//
// Pure observability layer over already-finalized Signal decision objects.
// This module does not fetch providers, re-run indicators, change thresholds,
// rank candidates, place orders, or grant execution authority.
//
// It answers WHY NOW / WHY PRICE / WHY SL / WHY TP / INVALIDATION using only
// fields already present on the existing decision object. Missing evidence is
// reported as MISSING/UNKNOWN rather than inferred or fabricated.

const KEY="v78016:entry_intelligence:signal";
const CAP=240;
const TTL_SEC=21600;

const finite=v=>Number.isFinite(Number(v))?Number(v):null;
const text=v=>v==null||v===""?null:String(v);
const first=(...xs)=>xs.find(x=>x!=null&&x!=="")??null;

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
  return {
    present:true,
    freshness:q.fresh===true?"LIVE":q.fresh===false?"STALE":"UNKNOWN",
    source:text(q.source),
    ageSec:finite(q.quoteAgeSec),
    price:finite(first(q.price,a?.currentPrice,a?.entry)),
  };
}

function plannedView(a){
  const p=a?.planned||a||{};
  return {
    entry:finite(first(p.entry,a?.entry)),
    sl:finite(first(p.sl,a?.sl)),
    tp:finite(first(p.tp2,p.tp1,p.tp,a?.tp2,a?.tp1,a?.tp)),
    rr:finite(first(p.targetRR,a?.targetRR,a?.rr)),
  };
}

function existingRegime(a){return first(a?.regime?.name,a?.regime,a?.method?.activeMode,a?.method?.family,a?.method?.profile,a?.canonical?.regime);}
function existingSession(a){return first(a?.session?.name,a?.session,a?.canonical?.session,a?.context?.session);}
function existingLocation(a){return first(a?.location?.label,a?.location,a?.entryPolicy?.location,a?.canonical?.location,a?.reason==="M15_LOCATION_REQUIRED"?"M15_LOCATION_REQUIRED":null);}
function existingTrigger(a){return first(a?.trigger?.label,a?.trigger,a?.entryPolicy?.trigger,a?.canonical?.trigger,a?.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED"?"M5_MSS_DISPLACEMENT_RETEST_REQUIRED":null);}

function marketSpecific(a,market){
  const c=a?.context||{},micro=c?.microstructure||{},canon=a?.canonical||{};
  if(market==="forex")return {
    session:first(existingSession(a),c?.forexSession),
    currencyStrength:first(c?.currencyStrength,a?.currencyStrength,canon?.currencyStrength),
    crossPairConfirmation:first(c?.crossPairConfirmation,c?.relativeStrength,a?.relativeStrength),
    eventSensitivity:first(canon?.news?.source,c?.news?.source),
  };
  if(market==="crypto")return {
    funding:first(micro?.funding,c?.funding,a?.funding),
    openInterest:first(micro?.openInterest,micro?.oi,c?.openInterest),
    longShort:first(micro?.longShort,c?.longShort),
    orderbook:first(micro?.orderbook,c?.orderbook),
    spread:first(micro?.spread,c?.spread,a?.spread),
    spotPerpIdentity:first(c?.instrumentIdentity,a?.instrumentType),
  };
  if(market==="metal")return {
    session:first(existingSession(a),c?.metalSession),
    usdContext:first(c?.usdContext,c?.dxy,canon?.usdContext),
    ratesContext:first(c?.ratesContext,c?.yields,canon?.ratesContext),
    volatilityContext:first(c?.volatilityRegime,a?.volatilityRegime),
  };
  if(market==="index")return {
    session:first(existingSession(a),c?.indexSession),
    instrumentIdentity:first(c?.instrumentIdentity,a?.instrumentType,"CASH_INDEX"),
    crossIndexConfirmation:first(c?.crossIndexConfirmation,c?.relativeStrength,a?.relativeStrength),
    riskContext:first(c?.riskSentiment,canon?.riskSentiment),
  };
  return {};
}

function completeness(obj){
  const vals=Object.values(obj||{}),known=vals.filter(v=>v!=null&&v!=="UNKNOWN"&&v!=="MISSING").length;
  return {known,total:vals.length,ratio:vals.length?Number((known/vals.length).toFixed(3)):0};
}

export function buildEntryIntelligenceShadow(a,{runtimeVersion=null,scanId=null}={}){
  if(!a?.symbol)return null;
  const market=marketOf(a),q=quoteView(a),p=plannedView(a),regime=existingRegime(a),session=existingSession(a),location=existingLocation(a),trigger=existingTrigger(a),specific=marketSpecific(a,market),now=Date.now();
  const hardBlocks=[];
  if(a?.status==="DATA_BLOCK")hardBlocks.push(a?.reason||a?.error||"DATA_BLOCK");
  if(a?.reason==="M15_LOCATION_REQUIRED")hardBlocks.push("M15_LOCATION_REQUIRED");
  if(a?.reason==="M5_MSS_DISPLACEMENT_RETEST_REQUIRED")hardBlocks.push("M5_MSS_DISPLACEMENT_RETEST_REQUIRED");
  if(a?.reason==="RR_QUALITY_REQUIRED")hardBlocks.push("RR_QUALITY_REQUIRED");
  if(q.freshness==="STALE")hardBlocks.push("QUOTE_STALE");

  const reasoning={
    whyNow:first(a?.reason,a?.method?.activeMode,a?.method?.profile,a?.status,"UNKNOWN"),
    whyPrice:p.entry!=null?`Existing planned entry ${p.entry}`:(q.price!=null?`Fresh-analysis reference ${q.price}`:"MISSING_ENTRY_EVIDENCE"),
    whySl:p.sl!=null?`Existing structural/plan SL ${p.sl}`:"MISSING_SL_EVIDENCE",
    whyTp:p.tp!=null?`Existing target ${p.tp}${p.rr!=null?` / RR ${p.rr}`:""}`:(p.rr!=null?`Existing RR ${p.rr}`:"MISSING_TP_RR_EVIDENCE"),
    invalidates:p.sl!=null?`Price invalidation at existing SL ${p.sl}`:first(a?.reason,"UNKNOWN"),
  };

  const core={regime,session,location,trigger,quoteFreshness:q.freshness,rr:p.rr,entry:p.entry,sl:p.sl,tp:p.tp};
  return {
    revision:"V78-016",
    createdAt:now,
    symbol:a.symbol,
    market,
    side:a.side||null,
    existingDecision:{status:a.status||"UNKNOWN",reason:a.reason||null,score:finite(a.score)},
    quote:q,
    plan:p,
    structure:{regime,session,location,trigger},
    marketSpecific:specific,
    reasoning,
    integrity:{core:completeness(core),marketSpecific:completeness(specific),missingCore:Object.entries(core).filter(([,v])=>v==null||v==="UNKNOWN"||v==="MISSING").map(([k])=>k),hardBlocks:[...new Set(hardBlocks)]},
    authority:{shadowOnly:true,changesDecision:false,executionAuthority:"NONE"},
    lineage:{runtimeVersion,scanId,sourceStatus:a.status||null},
  };
}

async function append(env,row){
  if(!env?.TRADING_STATE||!row)return;
  try{const old=await env.TRADING_STATE.get(KEY,"json"),rows=Array.isArray(old?.rows)?old.rows:[];rows.unshift(row);await env.TRADING_STATE.put(KEY,JSON.stringify({rows:rows.slice(0,CAP),updatedAt:Date.now()}),{expirationTtl:TTL_SEC});}catch{}
}

export async function recordEntryIntelligenceShadow(env,row){await append(env,row);}
export async function getEntryIntelligenceShadow(env,limit=20){try{const v=await env.TRADING_STATE?.get(KEY,"json");return (Array.isArray(v?.rows)?v.rows:[]).slice(0,limit);}catch{return [];}}
