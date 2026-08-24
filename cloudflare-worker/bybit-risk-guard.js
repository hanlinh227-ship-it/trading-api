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

function profitTargetGate(state={}){
  const t=state?.profitTarget;
  if(!t||String(t.status||"").toUpperCase()==="EXPIRED")return null;
  const target=num(t.targetUsd),baseline=num(t.baselineRealizedUsd),realized=num(state?.realizedUsd),pnl=realized-baseline,start=Date.parse(t.startAt||""),end=Date.parse(t.endAt||""),ts=Date.now();
  if(!(target>0)||!Number.isFinite(start)||!Number.isFinite(end)||ts<start||ts>end)return null;
  if(pnl+1e-9>=target)return {ok:false,reason:"PROFIT_TARGET_REACHED",targetUsd:target,baselineRealizedUsd:baseline,realizedUsd:realized,targetPnlUsd:pnl,remainingUsd:0,targetEndAt:t.endAt,policy:t.policy||"STOP_NEW_ENTRIES_ONLY"};
  return {ok:true,targetUsd:target,baselineRealizedUsd:baseline,realizedUsd:realized,targetPnlUsd:pnl,remainingUsd:Math.max(0,target-pnl),targetEndAt:t.endAt};
}

export function bybitRiskPreflight({cfg,equityUsd,state,candidateRiskUsd}){
  const equity=Math.max(0,num(equityUsd));
  if(!(equity>0))return {ok:false,reason:"EQUITY_INVALID"};
  const target=profitTargetGate(state);
  if(target?.ok===false)return target;
  const realized=num(state?.realizedUsd),openRiskUsd=computeOpenRiskUsd(state?.openPlans||{}),candidate=Math.max(0,num(candidateRiskUsd)),capUsd=equity*Math.max(0,num(cfg?.risk?.maxTotalOpenRiskPct))/100;
  if(openRiskUsd+candidate>capUsd+1e-9)return {ok:false,reason:"TOTAL_OPEN_RISK_CAP",openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,realizedUsd:realized,profitTarget:target};
  return {ok:true,realizedUsd:realized,openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,dailyLossStopEnabled:false,riskAccounting:"MANAGED_STOP_AWARE",profitTarget:target};
}

export function validateProtectionGeometry({side,entry,sl,tp}){
  const e=num(entry),s=num(sl),t=num(tp);
  if(!(e>0&&s>0&&t>0))return {ok:false,reason:"PROTECTION_PRICE_INVALID"};
  if(side==="Buy"&&!(s<e&&t>e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  if(side==="Sell"&&!(s>e&&t<e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  return {ok:true};
}
