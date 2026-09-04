// BTC-only adaptive full-account compounding + risk recycling. No martingale / no loser averaging.
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

export function drawdownState({equityUsd,highWaterUsd,cfg}){
  const equity=Math.max(0,num(equityUsd)),high=Math.max(equity,num(highWaterUsd)||equity),dd=high>0?(high-equity)/high*100:100;
  const ladder=[...(cfg?.risk?.drawdownGovernor||[])].sort((a,b)=>num(a.ddPct)-num(b.ddPct));let mult=1;
  for(const x of ladder)if(dd>=num(x.ddPct))mult=num(x.multiplier);
  return {equityUsd:equity,highWaterUsd:high,drawdownPct:dd,multiplier:clamp(mult,0,1),newRiskLocked:mult<=0};
}

export function capitalBaseState({equityUsd,walletBalanceUsd,cfg}){
  const equity=Math.max(0,num(equityUsd)),wallet=Math.max(0,num(walletBalanceUsd)||equity),c=cfg?.risk?.capitalBase||{};
  if(c.enabled===false)return {capitalBaseUsd:equity,walletBalanceUsd:wallet,equityUsd:equity,unrealizedProfitUsd:Math.max(0,equity-wallet),creditedUnrealizedUsd:Math.max(0,equity-wallet),creditPct:100};
  if(equity<=wallet&&c.useLowerOfBalanceAndEquityOnDrawdown!==false)return {capitalBaseUsd:equity,walletBalanceUsd:wallet,equityUsd:equity,unrealizedProfitUsd:0,creditedUnrealizedUsd:0,creditPct:0};
  const unrealized=Math.max(0,equity-wallet),creditPct=clamp(num(c.unrealizedProfitCreditPct)||25,0,50),credited=unrealized*creditPct/100,base=Math.min(equity,wallet+credited);
  return {capitalBaseUsd:Math.max(0,base),walletBalanceUsd:wallet,equityUsd:equity,unrealizedProfitUsd:unrealized,creditedUnrealizedUsd:credited,creditPct};
}

function lerp(a,b,t){return num(a)+(num(b)-num(a))*clamp(t,0,1);}
export function equityScaleState(equityUsd,cfg){
  const equity=Math.max(0,num(equityUsd)),s=cfg?.risk?.equityScale||{};
  if(!s.enabled)return {riskMult:1,marginCapPct:num(cfg?.risk?.maxPortfolioMarginPct||78),leverageBonus:0,tierEquityUsd:equity,continuous:true,lowerReferenceUsd:0,upperReferenceUsd:null,progressPct:100};
  const steps=[...(s.steps||[])].sort((a,b)=>num(a.equityUsd)-num(b.equityUsd));
  if(!steps.length)return {riskMult:1,marginCapPct:num(cfg?.risk?.maxPortfolioMarginPct||78),leverageBonus:0,tierEquityUsd:equity,continuous:true,lowerReferenceUsd:0,upperReferenceUsd:null,progressPct:100};
  const first=steps[0];
  if(equity<=num(first.equityUsd))return {riskMult:clamp(num(first.riskMult)||1,.5,num(s.maxRiskMult||1.4)),marginCapPct:clamp(num(first.marginCapPct)||num(cfg?.risk?.maxPortfolioMarginPct||78),30,num(s.maxMarginCapPct||84)),leverageBonus:Math.max(0,num(first.leverageBonus)),tierEquityUsd:equity,continuous:true,lowerReferenceUsd:num(first.equityUsd),upperReferenceUsd:steps[1]?num(steps[1].equityUsd):null,progressPct:0};
  for(let i=0;i<steps.length-1;i++){const a=steps[i],b=steps[i+1],lo=num(a.equityUsd),hi=Math.max(lo+1e-9,num(b.equityUsd));if(equity>=lo&&equity<hi){const t=(equity-lo)/(hi-lo);return {riskMult:clamp(lerp(a.riskMult,b.riskMult,t),.5,num(s.maxRiskMult||1.4)),marginCapPct:clamp(lerp(a.marginCapPct,b.marginCapPct,t),30,num(s.maxMarginCapPct||84)),leverageBonus:Math.max(0,lerp(a.leverageBonus,b.leverageBonus,t)),tierEquityUsd:equity,continuous:true,lowerReferenceUsd:lo,upperReferenceUsd:hi,progressPct:t*100};}}
  const last=steps.at(-1),tailStart=num(last.equityUsd),tailEnd=Math.max(tailStart+1,tailStart*2),t=clamp((equity-tailStart)/(tailEnd-tailStart),0,1);
  return {riskMult:clamp(lerp(last.riskMult,num(s.maxRiskMult||last.riskMult||1.4),t),.5,num(s.maxRiskMult||1.4)),marginCapPct:clamp(lerp(last.marginCapPct,num(s.maxMarginCapPct||last.marginCapPct||84),t),30,num(s.maxMarginCapPct||84)),leverageBonus:Math.max(0,num(last.leverageBonus)),tierEquityUsd:equity,continuous:true,lowerReferenceUsd:tailStart,upperReferenceUsd:t<1?tailEnd:null,progressPct:t*100};
}

export function trancheRiskUsd(t={}){const q=Math.abs(num(t.qty)),entry=num(t.entry),sl=num(t.managedSl||t.sl),side=String(t.side||'');if(!(q>0&&entry>0&&sl>0))return Math.max(0,num(t.initialRiskUsd||t.riskUsd));if(side==='Buy'&&sl>=entry)return 0;if(side==='Sell'&&sl<=entry)return 0;return Math.max(0,Math.abs(entry-sl)*q);}
export function activeRiskUsd(tranches=[]){return (tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN').reduce((s,t)=>s+trancheRiskUsd(t),0);}
export function aggregateSide(tranches=[]){const sides=[...new Set((tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN'&&Math.abs(num(t.qty))>0).map(t=>String(t.side||'')))].filter(Boolean);return sides.length===1?sides[0]:sides.length?'MIXED':null;}
export function highWaterFromState(state={},equityUsd=0){return Math.max(num(equityUsd),num(state.highWaterUsd),num(state.protectedEquityUsd));}

function riskPctForStrength(cfg,strength){const r=cfg?.risk||{};if(strength==='A_PLUS')return num(r.aPlusEntryRiskPct||1.5);if(strength==='STRONG')return num(r.strongEntryRiskPct||1.2);return num(r.baseEntryRiskPct||.85);}
function tierRank(t){return String(t||'CONFIRM')==='PROBE'?1:String(t||'CONFIRM')==='FULL'?3:2;}
function tierRiskFactor(setup={}){const explicit=num(setup?.riskScale);if(explicit>0)return clamp(explicit,.35,1);const t=String(setup?.entryTier||'CONFIRM');return t==='PROBE'?.55:t==='CONFIRM'?.82:1;}
function aggregateEntry(tranches=[],side){let q=0,n=0;for(const t of tranches||[]){if(String(t.status||'OPEN')==='OPEN'&&String(t.side||'')===side){const x=Math.abs(num(t.qty)),e=num(t.entry);q+=x;n+=x*e;}}return q>0?n/q:0;}
function newestOpen(tranches=[]){return [...(tranches||[])].filter(t=>String(t.status||'OPEN')==='OPEN').sort((a,b)=>num(b.createdAt)-num(a.createdAt))[0]||null;}

export function btcRiskDecision({cfg,equityUsd,state={},setup,markPrice,candidateInitialMarginUsd=0,candidateActualRiskUsd=0}){
  const equity=Math.max(0,num(equityUsd));if(!(equity>0))return {ok:false,reason:'EQUITY_INVALID'};
  const wallet=Math.max(0,num(state.lastWalletBalanceUsd)||equity),capital=capitalBaseState({equityUsd:equity,walletBalanceUsd:wallet,cfg});if(!(capital.capitalBaseUsd>0))return {ok:false,reason:'CAPITAL_BASE_INVALID',capital};
  const tranches=Array.isArray(state.tranches)?state.tranches:[],highWater=highWaterFromState(state,equity),dd=drawdownState({equityUsd:equity,highWaterUsd:highWater,cfg}),scale=equityScaleState(capital.capitalBaseUsd,cfg);
  if(dd.newRiskLocked)return {ok:false,reason:'DRAWDOWN_NEW_RISK_LOCK',...dd,scale,capital};
  const side=String(setup?.side||''),entryTier=String(setup?.entryTier||'CONFIRM'),existingSide=aggregateSide(tranches);if(existingSide&&existingSide!==side)return {ok:false,reason:'OPPOSITE_EXPOSURE_REQUIRES_FLAT_OR_EXPLICIT_REVERSAL',existingSide,candidateSide:side};
  const avgEntry=aggregateEntry(tranches,side),mark=num(markPrice||setup?.entry),openSame=tranches.filter(t=>String(t.status||'OPEN')==='OPEN'&&String(t.side||'')===side);
  if(openSame.length&&avgEntry>0){
    const profitable=side==='Buy'?mark>=avgEntry:mark<=avgEntry;if(!profitable)return {ok:false,reason:'NO_ADD_TO_LOSER',averageEntry:avgEntry,markPrice:mark};
    const newest=newestOpen(tranches),newestTier=String(newest?.entryTier||'CONFIRM');if(newestTier==='PROBE'&&entryTier==='PROBE')return {ok:false,reason:'PROBE_ALREADY_ACTIVE_WAIT_CONFIRMATION',newestTrancheId:newest?.id||null};
    const initial=Math.max(.01,num(newest?.initialRiskUsd||newest?.riskUsd)),remaining=newest?trancheRiskUsd(newest):0,thresholdPct=clamp(num(cfg?.risk?.priorRiskProtectionThresholdPct||30),5,75),threshold=thresholdPct/100,stopDist=Math.max(1e-9,Math.abs(num(newest?.entry)-num(newest?.sl))),favour=side==='Buy'?mark-num(newest?.entry):num(newest?.entry)-mark,favourR=favour/stopDist,upgrade=tierRank(entryTier)>tierRank(newestTier),upgradeMinR=clamp(num(cfg?.risk?.tierUpgradeMinR)||.18,.05,.60),upgradeRemaining=clamp(num(cfg?.risk?.tierUpgradeMaxRemainingRiskPct)||70,20,90)/100,protectedNewest=remaining<=initial*threshold,upgradeReady=upgrade&&(favourR>=upgradeMinR||remaining<=initial*upgradeRemaining);
    if(!protectedNewest&&!upgradeReady)return {ok:false,reason:upgrade?'TIER_UPGRADE_WAIT_MARKET_CONFIRMATION':'PYRAMID_WAIT_PRIOR_RISK_PROTECTION',newestTrancheId:newest?.id||null,newestTier,candidateTier:entryTier,newestRiskUsd:remaining,initialRiskUsd:initial,favourR,requiredUpgradeR:upgradeMinR,requiredRemainingRiskPct:upgrade?upgradeRemaining*100:thresholdPct};
  }
  const absolutePct=Math.max(0,num(cfg?.risk?.absoluteSingleEntryRiskPct||1.6)),tierFactor=tierRiskFactor(setup),basePct=Math.min(absolutePct,riskPctForStrength(cfg,String(setup?.strength||'NORMAL'))*tierFactor),riskPct=Math.min(absolutePct,basePct*scale.riskMult)*dd.multiplier,candidateRiskUsd=capital.capitalBaseUsd*riskPct/100,actualCandidateRisk=Math.max(0,num(candidateActualRiskUsd))||candidateRiskUsd,active=activeRiskUsd(tranches),normalCap=capital.capitalBaseUsd*num(cfg?.risk?.maxActiveRiskPct||7.5)/100,tempCap=capital.capitalBaseUsd*num(cfg?.risk?.temporaryAPlusActiveRiskPct||9.5)/100,cap=String(setup?.strength)==='A_PLUS'?Math.max(normalCap,tempCap):normalCap,singleRiskCapUsd=capital.capitalBaseUsd*absolutePct/100*dd.multiplier,remainingActiveRiskCapacityUsd=Math.max(0,cap-active),maxCandidateRiskUsd=Math.max(0,Math.min(singleRiskCapUsd,remainingActiveRiskCapacityUsd));
  if(actualCandidateRisk>maxCandidateRiskUsd+1e-9)return {ok:false,reason:'ACTIVE_RISK_BUDGET_EXHAUSTED',activeRiskUsd:active,candidateRiskUsd,actualCandidateRiskUsd:actualCandidateRisk,projectedRiskUsd:active+actualCandidateRisk,capUsd:cap,singleRiskCapUsd,remainingActiveRiskCapacityUsd,maxCandidateRiskUsd,riskPct,entryTier,tierFactor,...dd,scale,capital};
  const marginCap=capital.capitalBaseUsd*scale.marginCapPct/100,openMargin=(tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN').reduce((s,t)=>s+Math.max(0,num(t.initialMarginUsd)),0),candidateMargin=Math.max(0,num(candidateInitialMarginUsd));
  if(candidateMargin>0&&openMargin+candidateMargin>marginCap+1e-9)return {ok:false,reason:'PORTFOLIO_MARGIN_CAP',openMarginUsd:openMargin,candidateMarginUsd:candidateMargin,marginCapUsd:marginCap,marginCapPct:scale.marginCapPct,scale,capital};
  return {ok:true,riskPct,candidateRiskUsd,actualCandidateRiskUsd:actualCandidateRisk,activeRiskUsd:active,projectedRiskUsd:active+actualCandidateRisk,capUsd:cap,singleRiskCapUsd,remainingActiveRiskCapacityUsd,maxCandidateRiskUsd,openMarginUsd:openMargin,marginCapUsd:marginCap,marginCapPct:scale.marginCapPct,entryTier,tierFactor,...dd,scale,capital,pyramiding:openSame.length>0,riskRecycling:true,dailyTradeQuota:false,fullAccountAuthority:true};
}

function ceilStep(v,step){return Math.ceil((Number(v)-1e-12)/step)*step;}
function floorStep(v,step){return Math.floor((Number(v)+1e-12)/step)*step;}
export function sizeBtcSetup({setup,riskUsd,maxRiskUsd=0,filters={},leverage=5,equityUsd=0,capitalBaseUsd=0,marginCapPct=78}){
  const entry=Math.max(0,num(setup?.entry)),stop=Math.abs(entry-num(setup?.sl)),target=Math.max(0,num(riskUsd));if(!(entry>0&&stop>0&&target>0))return {ok:false,reason:'STOP_OR_RISK_INVALID'};
  const step=Math.max(1e-12,num(filters.qtyStep)||.001),minQty=Math.max(step,num(filters.minQty)||step),maxQty=Math.max(minQty,num(filters.maxQty)||1e9),minNotional=Math.max(0,num(filters.minNotional)||5),capital=Math.max(0,num(capitalBaseUsd)||num(equityUsd)),marginCapUsd=capital*clamp(num(marginCapPct)||78,30,84)/100,hardRiskCap=Math.max(target,num(maxRiskUsd)||target*1.20),strength=String(setup?.strength||'NORMAL'),tier=String(setup?.entryTier||'CONFIRM'),softMult=tier==='PROBE'?1.16:tier==='CONFIRM'?1.28:strength==='A_PLUS'?1.45:strength==='STRONG'?1.35:1.30,softRiskCap=Math.min(hardRiskCap,target*softMult),raw=target/stop;
  const minByNotional=ceilStep(minNotional/entry,step),minimum=Math.min(maxQty,Math.max(minQty,minByNotional)),floorQty=Math.min(maxQty,Math.max(minimum,floorStep(raw,step))),ceilQty=Math.min(maxQty,Math.max(minimum,ceilStep(raw,step))),candidates=[minimum,floorQty,ceilQty].filter((v,i,a)=>v>0&&a.findIndex(x=>Math.abs(x-v)<step/1000)===i).map(q=>{const notional=q*entry,priceRisk=q*stop,initialMargin=notional/Math.max(1,num(leverage)),costBps=Math.max(0,num(setup?.cost?.totalCostBps||setup?.cost?.baseRoundTripCostBps)),costReserve=notional*costBps/10000;return {qty:q,notionalUsd:notional,actualRiskUsd:priceRisk,priceRiskUsd:priceRisk,costReserveUsd:costReserve,effectiveLossEstimateUsd:priceRisk+costReserve,initialMarginUsd:initialMargin,leverage,capitalBaseUsd:capital,marginCapPct};});
  const riskFeasible=candidates.filter(x=>x.actualRiskUsd<=softRiskCap+1e-9&&x.initialMarginUsd<=marginCapUsd+1e-9);
  if(!riskFeasible.length){const min=candidates.sort((a,b)=>a.qty-b.qty)[0];if(min&&min.actualRiskUsd>hardRiskCap+1e-9)return {ok:false,reason:'MIN_QTY_EXCEEDS_HARD_RISK_CAP',qty:min.qty,actualRiskUsd:min.actualRiskUsd,targetRiskUsd:target,softRiskCapUsd:softRiskCap,hardRiskCapUsd:hardRiskCap};if(min&&min.initialMarginUsd>marginCapUsd+1e-9)return {ok:false,reason:'POSITION_MARGIN_TOO_LARGE',qty:min.qty,initialMarginUsd:min.initialMarginUsd,marginCapUsd,marginCapPct,capitalBaseUsd:capital};return {ok:false,reason:'QUANTIZED_SIZE_OUTSIDE_ADAPTIVE_RISK_BAND',targetRiskUsd:target,softRiskCapUsd:softRiskCap,hardRiskCapUsd:hardRiskCap,candidates};}
  let chosen=riskFeasible.sort((a,b)=>Math.abs(a.actualRiskUsd-target)-Math.abs(b.actualRiskUsd-target))[0];if(tier!=='PROBE'&&strength!=='NORMAL'){const higher=riskFeasible.filter(x=>x.actualRiskUsd>=target).sort((a,b)=>a.actualRiskUsd-b.actualRiskUsd)[0];if(higher&&chosen.actualRiskUsd<target*.78)chosen=higher;}
  return {ok:true,...chosen,targetRiskUsd:target,softRiskCapUsd:softRiskCap,hardRiskCapUsd:hardRiskCap,quantized:true,qtyStep:step,minQty,entryTier:tier,selectionPolicy:'TIER_AWARE_NEAREST_TARGET_WITH_HARD_RISK_AND_MARGIN_CAP'};
}

export function addTranche(state={},x={}){const tranches=Array.isArray(state.tranches)?[...state.tranches]:[],id=String(x.id||`BTC-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`),row={symbol:'BTCUSDT',status:'OPEN',createdAt:Date.now(),managedSl:x.sl,protected:false,entryTier:String(x.entryTier||'CONFIRM'),...x,id};tranches.push(row);return {...state,tranches,highWaterUsd:Math.max(num(state.highWaterUsd),num(x.equityUsd)),lastTrancheId:id};}
export function updateTrancheProtection(state={},id,managedSl){const tranches=(state.tranches||[]).map(t=>{if(String(t.id)!==String(id))return t;const protectedNow=String(t.side)==='Buy'?num(managedSl)>=num(t.entry):num(managedSl)<=num(t.entry);return {...t,managedSl:num(managedSl),protected:protectedNow||t.protected};});return {...state,tranches};}
export function closeAllTranches(state={},meta={}){const tranches=(state.tranches||[]).map(t=>String(t.status||'OPEN')==='OPEN'?{...t,status:'CLOSED',closedAt:Date.now(),...meta}:t);return {...state,tranches,previousAdaptiveProtection:state.lastAdaptiveProtection||state.previousAdaptiveProtection||null,lastAdaptiveProtection:null,aggregateStop:0,virtualTarget:0,positionPeakR:0,invalidationCount:0,currentPositionMarginUsd:0,currentPositionLeverage:0,openPlans:{}};}

export const BTC_RISK_ENGINE_VERSION='BTC_RISK_RECYCLE_V7_TIERED_SMART_QUANTIZED_SIZING';
