const num=v=>Number.isFinite(Number(v))?Number(v):0;

function effectiveStop(p={}){
  const managed=num(p?.managedSl),initial=num(p?.sl),entry=num(p?.entry),side=String(p?.side||"");
  if(!(managed>0))return initial;
  // A managed stop may only reduce risk relative to the initial stop. Ignore any malformed
  // value that would loosen the position so accounting never understates actual open risk.
  if(side==="Buy"&&managed>=initial&&managed<=entry)return managed;
  if(side==="Sell"&&managed<=initial&&managed>=entry)return managed;
  // Once the stop has crossed entry, remaining downside risk is zero; locked profit is not
  // counted as negative risk or extra capacity.
  if(side==="Buy"&&managed>entry)return managed;
  if(side==="Sell"&&managed<entry)return managed;
  return initial;
}

export function computeOpenRiskUsd(openPlans={}){
  let total=0;
  for(const p of Object.values(openPlans||{})){
    const q=Math.abs(num(p?.qty)),entry=num(p?.entry),sl=effectiveStop(p);
    if(q>0&&entry>0&&sl>0){
      const side=String(p?.side||"");
      let riskPerUnit=Math.abs(entry-sl);
      if(side==="Buy"&&sl>=entry)riskPerUnit=0;
      if(side==="Sell"&&sl<=entry)riskPerUnit=0;
      total+=Math.max(0,riskPerUnit*q);
    }else if(num(p?.riskUsd)>0)total+=num(p.riskUsd);
  }
  return total;
}

export function bybitRiskPreflight({cfg,equityUsd,state,candidateRiskUsd}){
  const equity=Math.max(0,num(equityUsd));
  if(!(equity>0))return {ok:false,reason:"EQUITY_INVALID"};
  const realized=num(state?.realizedUsd),openRiskUsd=computeOpenRiskUsd(state?.openPlans||{}),candidate=Math.max(0,num(candidateRiskUsd)),capUsd=equity*Math.max(0,num(cfg?.risk?.maxTotalOpenRiskPct))/100;
  if(openRiskUsd+candidate>capUsd+1e-9)return {ok:false,reason:"TOTAL_OPEN_RISK_CAP",openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,realizedUsd:realized};
  return {ok:true,realizedUsd:realized,openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,dailyLossStopEnabled:false,riskAccounting:"MANAGED_STOP_AWARE"};
}

export function validateProtectionGeometry({side,entry,sl,tp}){
  const e=num(entry),s=num(sl),t=num(tp);
  if(!(e>0&&s>0&&t>0))return {ok:false,reason:"PROTECTION_PRICE_INVALID"};
  if(side==="Buy"&&!(s<e&&t>e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  if(side==="Sell"&&!(s>e&&t<e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  return {ok:true};
}
