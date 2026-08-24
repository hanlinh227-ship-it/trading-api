// Maximum three concurrent scalp positions with duplicate-direction and total-risk guards.

function sideOfPosition(p){const amt=Number(p?.positionAmt||0);return amt>0?"BUY":amt<0?"SELL":null;}

export function positionExposure(positions=[]){
  const open=(positions||[]).filter(x=>Math.abs(Number(x?.positionAmt||0))>0);
  const longs=open.filter(x=>sideOfPosition(x)==="BUY");
  const shorts=open.filter(x=>sideOfPosition(x)==="SELL");
  return {open,longCount:longs.length,shortCount:shorts.length,symbols:new Set(open.map(x=>String(x.symbol||"").toUpperCase()))};
}

export function chooseCandidateForSlots(candidates=[],positions=[],cfg={}){
  const ex=positionExposure(positions),maxOpen=Math.min(3,Number(cfg.maxOpenPositions||3)),maxSame=Math.min(2,Number(cfg?.risk?.maxSameDirectionPositions||2));
  if(ex.open.length>=maxOpen)return {candidate:null,reason:"MAX_OPEN_POSITIONS",exposure:{open:ex.open.length,longCount:ex.longCount,shortCount:ex.shortCount}};
  for(const c of candidates||[]){
    const sym=String(c?.symbol||"").toUpperCase(),side=String(c?.side||"").toUpperCase();
    if(!sym||!side||ex.symbols.has(sym))continue;
    if(side==="BUY"&&ex.longCount>=maxSame)continue;
    if(side==="SELL"&&ex.shortCount>=maxSame)continue;
    return {candidate:c,reason:"SLOT_AVAILABLE",exposure:{open:ex.open.length,longCount:ex.longCount,shortCount:ex.shortCount}};
  }
  return {candidate:null,reason:"NO_NON_DUPLICATE_SLOT_CANDIDATE",exposure:{open:ex.open.length,longCount:ex.longCount,shortCount:ex.shortCount}};
}

export function totalOpenRiskGuard({openPlans={},candidateRiskUsd=0,equityUsd=0,cfg={}}={}){
  const plans=Object.values(openPlans||{}),openRiskUsd=plans.reduce((s,p)=>s+Math.max(0,Number(p?.riskUsd||0)),0),candidate=Math.max(0,Number(candidateRiskUsd||0)),equity=Math.max(0,Number(equityUsd||0));
  const capPct=Math.max(5,Number(cfg?.risk?.maxTotalOpenRiskPct||30)),capUsd=equity>0?equity*capPct/100:0,projected=openRiskUsd+candidate;
  if(!(candidate>0))return {ok:false,reason:"CANDIDATE_RISK_INVALID",openRiskUsd,candidateRiskUsd:candidate,projectedRiskUsd:projected,capUsd,capPct};
  if(!(equity>0)||!(capUsd>0))return {ok:false,reason:"EQUITY_INVALID_FOR_TOTAL_RISK",openRiskUsd,candidateRiskUsd:candidate,projectedRiskUsd:projected,capUsd,capPct};
  if(projected>capUsd+1e-9)return {ok:false,reason:"TOTAL_OPEN_RISK_CAP",openRiskUsd,candidateRiskUsd:candidate,projectedRiskUsd:projected,projectedRiskPct:projected/equity*100,capUsd,capPct};
  return {ok:true,reason:"TOTAL_OPEN_RISK_OK",openRiskUsd,candidateRiskUsd:candidate,projectedRiskUsd:projected,projectedRiskPct:projected/equity*100,capUsd,capPct,remainingRiskUsd:Math.max(0,capUsd-projected)};
}
