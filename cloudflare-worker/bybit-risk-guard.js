const num=v=>Number.isFinite(Number(v))?Number(v):0;

export function computeOpenRiskUsd(openPlans={}){
  let total=0;
  for(const p of Object.values(openPlans||{})){
    const q=Math.abs(num(p?.qty));
    const entry=num(p?.entry),sl=num(p?.sl);
    if(q>0&&entry>0&&sl>0)total+=Math.abs(entry-sl)*q;
    else if(num(p?.riskUsd)>0)total+=num(p.riskUsd);
  }
  return total;
}

export function bybitRiskPreflight({cfg,equityUsd,state,candidateRiskUsd}){
  const equity=Math.max(0,num(equityUsd));
  if(!(equity>0))return {ok:false,reason:"EQUITY_INVALID"};
  const realized=num(state?.realizedUsd);
  const openRiskUsd=computeOpenRiskUsd(state?.openPlans||{}),candidate=Math.max(0,num(candidateRiskUsd)),capUsd=equity*Math.max(0,num(cfg?.risk?.maxTotalOpenRiskPct))/100;
  if(openRiskUsd+candidate>capUsd+1e-9)return {ok:false,reason:"TOTAL_OPEN_RISK_CAP",openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,realizedUsd:realized};
  return {ok:true,realizedUsd:realized,openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,dailyLossStopEnabled:false};
}

export function validateProtectionGeometry({side,entry,sl,tp}){
  const e=num(entry),s=num(sl),t=num(tp);
  if(!(e>0&&s>0&&t>0))return {ok:false,reason:"PROTECTION_PRICE_INVALID"};
  if(side==="Buy"&&!(s<e&&t>e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  if(side==="Sell"&&!(s>e&&t<e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  return {ok:true};
}
