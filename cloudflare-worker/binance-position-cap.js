// Maximum three concurrent scalp positions with duplicate-direction guard.

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
