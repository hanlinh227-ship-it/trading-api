const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function equityRiskCurvePct(equity,cfg){const r=cfg?.risk||{},anchor=Math.max(.5,num(r.riskCurveAnchorEquityUsd)||25),small=Math.max(.1,num(r.riskCurveSmallPct)||6),floor=Math.max(.1,num(r.riskCurveLargeFloorPct)||.75),decay=Math.max(.1,num(r.riskCurveDecayPerDecade)||1.25),decades=Math.log10(Math.max(1,equity/anchor));return clamp(small-decay*decades,floor,small); }

function effectiveStop(p={}){
  const managed=num(p?.managedSl),initial=num(p?.sl),entry=num(p?.entry),side=String(p?.side||"");
  if(!(managed>0))return initial;
  if(side==="Buy"&&managed>=initial&&managed<=entry)return managed;
  if(side==="Sell"&&managed<=initial&&managed>=entry)return managed;
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

export function computeOpenInitialMarginUsd(openPlans={}){
  let total=0;
  for(const p of Object.values(openPlans||{})){
    const explicit=num(p?.margin?.initialMarginUsd);
    if(explicit>0){total+=explicit;continue;}
    const notional=num(p?.margin?.notional)||Math.abs(num(p?.qty))*num(p?.entry),lev=num(p?.leverage);
    if(notional>0&&lev>0)total+=notional/lev;
  }
  return total;
}

export function bybitRiskPreflight({cfg,equityUsd,state,candidateRiskUsd,candidateInitialMarginUsd=0}){
  const equity=Math.max(0,num(equityUsd));
  if(!(equity>0))return {ok:false,reason:"EQUITY_INVALID"};
  const realized=num(state?.realizedUsd),openPlans=state?.openPlans||{},openRiskUsd=computeOpenRiskUsd(openPlans),candidate=Math.max(0,num(candidateRiskUsd));
  const targetRiskPct=equityRiskCurvePct(equity,cfg),configuredSinglePct=Math.max(.1,num(cfg?.risk?.maxRiskPctOfEquity)||8),singleRiskPct=Math.min(configuredSinglePct,Math.max(targetRiskPct,targetRiskPct*1.35)),singleCapUsd=equity*singleRiskPct/100;
  if(candidate>singleCapUsd+1e-9)return {ok:false,reason:"SINGLE_TRADE_RISK_CAP",candidateRiskUsd:candidate,singleCapUsd,equityUsd:equity};
  const configuredTotalPct=Math.max(4,num(cfg?.risk?.maxTotalOpenRiskPct)||24),totalOpenRiskPct=Math.min(configuredTotalPct,Math.max(4,targetRiskPct*4)),capUsd=equity*totalOpenRiskPct/100;
  if(openRiskUsd+candidate>capUsd+1e-9)return {ok:false,reason:"TOTAL_OPEN_RISK_CAP",openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,realizedUsd:realized};

  const openInitialMarginUsd=computeOpenInitialMarginUsd(openPlans),portfolioMarginCapUsd=equity*Math.max(0,num(cfg?.risk?.maxPortfolioMarginPct))/100;
  const providedMarginUsd=Math.max(0,num(candidateInitialMarginUsd)),fallbackSlotMarginUsd=candidate>0?equity*Math.max(0,num(cfg?.risk?.maxMarginPerPositionPct))/100:0,candidateMarginUsd=providedMarginUsd>0?providedMarginUsd:fallbackSlotMarginUsd;
  if(candidateMarginUsd>0&&openInitialMarginUsd+candidateMarginUsd>portfolioMarginCapUsd+1e-9){
    return {ok:false,reason:"PORTFOLIO_MARGIN_HEADROOM",openInitialMarginUsd,candidateMarginUsd,projectedInitialMarginUsd:openInitialMarginUsd+candidateMarginUsd,portfolioMarginCapUsd,equityUsd:equity,marginSource:providedMarginUsd>0?"ACTUAL_CANDIDATE":"FAIL_SAFE_SLOT_FALLBACK",managementOnly:true};
  }
  return {ok:true,realizedUsd:realized,openRiskUsd,candidateRiskUsd:candidate,totalRiskUsd:openRiskUsd+candidate,capUsd,singleCapUsd,targetRiskPct,singleRiskPct,totalOpenRiskPct,openInitialMarginUsd,candidateMarginUsd,portfolioMarginCapUsd,dailyLossStopEnabled:false,dailyTargetEnabled:false,continuousTrading:true,riskAccounting:"MANAGED_STOP_AWARE_EQUITY_CURVE_V188",marginAccounting:providedMarginUsd>0?"ACTUAL_CANDIDATE_INITIAL_MARGIN_V188":"FAIL_SAFE_SLOT_FALLBACK"};
}

export function validateProtectionGeometry({side,entry,sl,tp}){
  const e=num(entry),s=num(sl),t=num(tp);
  if(!(e>0&&s>0&&t>0))return {ok:false,reason:"PROTECTION_PRICE_INVALID"};
  if(side==="Buy"&&!(s<e&&t>e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  if(side==="Sell"&&!(s>e&&t<e))return {ok:false,reason:"PROTECTION_GEOMETRY_INVALID"};
  return {ok:true};
}
