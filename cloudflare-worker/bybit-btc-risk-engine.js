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

export function equityScaleState(equityUsd,cfg){
  const equity=Math.max(0,num(equityUsd)),s=cfg?.risk?.equityScale||{};
  if(!s.enabled)return {riskMult:1,marginCapPct:num(cfg?.risk?.maxPortfolioMarginPct||78),leverageBonus:0,tierEquityUsd:0};
  const steps=[...(s.steps||[])].sort((a,b)=>num(a.equityUsd)-num(b.equityUsd));let row={riskMult:1,marginCapPct:num(cfg?.risk?.maxPortfolioMarginPct||78),leverageBonus:0,equityUsd:0};
  for(const x of steps)if(equity>=num(x.equityUsd))row=x;
  return {riskMult:clamp(num(row.riskMult)||1,.5,num(s.maxRiskMult||1.4)),marginCapPct:clamp(num(row.marginCapPct)||num(cfg?.risk?.maxPortfolioMarginPct||78),30,num(s.maxMarginCapPct||84)),leverageBonus:Math.max(0,Math.round(num(row.leverageBonus))),tierEquityUsd:num(row.equityUsd)};
}

export function trancheRiskUsd(t={}){
  const q=Math.abs(num(t.qty)),entry=num(t.entry),sl=num(t.managedSl||t.sl),side=String(t.side||'');
  if(!(q>0&&entry>0&&sl>0))return Math.max(0,num(t.initialRiskUsd||t.riskUsd));
  if(side==='Buy'&&sl>=entry)return 0;if(side==='Sell'&&sl<=entry)return 0;
  return Math.max(0,Math.abs(entry-sl)*q);
}
export function activeRiskUsd(tranches=[]){return (tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN').reduce((s,t)=>s+trancheRiskUsd(t),0);}
export function aggregateSide(tranches=[]){const sides=[...new Set((tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN'&&Math.abs(num(t.qty))>0).map(t=>String(t.side||'')))].filter(Boolean);return sides.length===1?sides[0]:sides.length?'MIXED':null;}
export function highWaterFromState(state={},equityUsd=0){return Math.max(num(equityUsd),num(state.highWaterUsd),num(state.protectedEquityUsd));}

function riskPctForStrength(cfg,strength){const r=cfg?.risk||{};if(strength==='A_PLUS')return num(r.aPlusEntryRiskPct||1.5);if(strength==='STRONG')return num(r.strongEntryRiskPct||1.2);return num(r.baseEntryRiskPct||.85);}
function aggregateEntry(tranches=[],side){let q=0,n=0;for(const t of tranches||[]){if(String(t.status||'OPEN')==='OPEN'&&String(t.side||'')===side){const x=Math.abs(num(t.qty)),e=num(t.entry);q+=x;n+=x*e;}}return q>0?n/q:0;}
function newestOpen(tranches=[]){return [...(tranches||[])].filter(t=>String(t.status||'OPEN')==='OPEN').sort((a,b)=>num(b.createdAt)-num(a.createdAt))[0]||null;}

export function btcRiskDecision({cfg,equityUsd,state={},setup,markPrice,candidateInitialMarginUsd=0}){
  const equity=Math.max(0,num(equityUsd));if(!(equity>0))return {ok:false,reason:'EQUITY_INVALID'};
  const wallet=Math.max(0,num(state.lastWalletBalanceUsd)||equity),capital=capitalBaseState({equityUsd:equity,walletBalanceUsd:wallet,cfg});if(!(capital.capitalBaseUsd>0))return {ok:false,reason:'CAPITAL_BASE_INVALID',capital};
  const tranches=Array.isArray(state.tranches)?state.tranches:[],highWater=highWaterFromState(state,equity),dd=drawdownState({equityUsd:equity,highWaterUsd:highWater,cfg}),scale=equityScaleState(capital.capitalBaseUsd,cfg);
  if(dd.newRiskLocked)return {ok:false,reason:'DRAWDOWN_NEW_RISK_LOCK',...dd,scale,capital};
  const side=String(setup?.side||''),existingSide=aggregateSide(tranches);if(existingSide&&existingSide!==side)return {ok:false,reason:'OPPOSITE_EXPOSURE_REQUIRES_FLAT_OR_EXPLICIT_REVERSAL',existingSide,candidateSide:side};

  const avgEntry=aggregateEntry(tranches,side),mark=num(markPrice||setup?.entry),openSame=tranches.filter(t=>String(t.status||'OPEN')==='OPEN'&&String(t.side||'')===side);
  if(openSame.length&&avgEntry>0){
    const profitable=side==='Buy'?mark>=avgEntry:mark<=avgEntry;
    if(!profitable)return {ok:false,reason:'NO_ADD_TO_LOSER',averageEntry:avgEntry,markPrice:mark};
    const newest=newestOpen(tranches),thresholdPct=clamp(num(cfg?.risk?.priorRiskProtectionThresholdPct||30),5,60),threshold=thresholdPct/100;
    const initial=Math.max(.01,num(newest?.initialRiskUsd||newest?.riskUsd)),remaining=newest?trancheRiskUsd(newest):0,protectedNewest=newest?remaining<=initial*threshold:true;
    if(!protectedNewest)return {ok:false,reason:'PYRAMID_WAIT_PRIOR_RISK_PROTECTION',newestTrancheId:newest?.id||null,newestRiskUsd:remaining,initialRiskUsd:initial,requiredRemainingRiskPct:thresholdPct};
  }

  const basePct=Math.min(num(cfg?.risk?.absoluteSingleEntryRiskPct||1.6),riskPctForStrength(cfg,String(setup?.strength||'NORMAL'))),riskPct=Math.min(num(cfg?.risk?.absoluteSingleEntryRiskPct||1.6),basePct*scale.riskMult)*dd.multiplier,candidateRiskUsd=capital.capitalBaseUsd*riskPct/100,active=activeRiskUsd(tranches),normalCap=capital.capitalBaseUsd*num(cfg?.risk?.maxActiveRiskPct||7.5)/100,tempCap=capital.capitalBaseUsd*num(cfg?.risk?.temporaryAPlusActiveRiskPct||9.5)/100,cap=String(setup?.strength)==='A_PLUS'?Math.max(normalCap,tempCap):normalCap;
  if(active+candidateRiskUsd>cap+1e-9)return {ok:false,reason:'ACTIVE_RISK_BUDGET_EXHAUSTED',activeRiskUsd:active,candidateRiskUsd,projectedRiskUsd:active+candidateRiskUsd,capUsd:cap,riskPct,...dd,scale,capital};
  const marginCap=capital.capitalBaseUsd*scale.marginCapPct/100,openMargin=(tranches||[]).filter(t=>String(t.status||'OPEN')==='OPEN').reduce((s,t)=>s+Math.max(0,num(t.initialMarginUsd)),0),candidateMargin=Math.max(0,num(candidateInitialMarginUsd));
  if(candidateMargin>0&&openMargin+candidateMargin>marginCap+1e-9)return {ok:false,reason:'PORTFOLIO_MARGIN_CAP',openMarginUsd:openMargin,candidateMarginUsd:candidateMargin,marginCapUsd:marginCap,marginCapPct:scale.marginCapPct,scale,capital};
  return {ok:true,riskPct,candidateRiskUsd,activeRiskUsd:active,projectedRiskUsd:active+candidateRiskUsd,capUsd:cap,openMarginUsd:openMargin,marginCapUsd:marginCap,marginCapPct:scale.marginCapPct,...dd,scale,capital,pyramiding:openSame.length>0,riskRecycling:true,dailyTradeQuota:false,fullAccountAuthority:true};
}

export function sizeBtcSetup({setup,riskUsd,filters={},leverage=5,equityUsd=0,capitalBaseUsd=0,marginCapPct=78}){
  const stop=Math.abs(num(setup?.entry)-num(setup?.sl));if(!(stop>0&&riskUsd>0))return {ok:false,reason:'STOP_OR_RISK_INVALID'};
  const step=Math.max(1e-12,num(filters.qtyStep)||.001),minQty=Math.max(0,num(filters.minQty)||.001),maxQty=Math.max(minQty,num(filters.maxQty)||1e9),minNotional=Math.max(0,num(filters.minNotional)||5),raw=num(riskUsd)/stop;
  let qty=Math.floor((raw+1e-12)/step)*step;qty=Math.min(qty,maxQty);if(qty<minQty)qty=minQty;let notional=qty*num(setup.entry);if(notional<minNotional){qty=Math.ceil((minNotional/num(setup.entry))/step)*step;notional=qty*num(setup.entry);}
  const actualRisk=qty*stop,initialMargin=notional/Math.max(1,num(leverage)),capital=Math.max(0,num(capitalBaseUsd)||num(equityUsd));if(actualRisk>riskUsd*1.20)return {ok:false,reason:'MIN_QTY_EXCEEDS_RISK_BUDGET',qty,actualRiskUsd:actualRisk,targetRiskUsd:riskUsd};
  if(initialMargin>capital*clamp(num(marginCapPct)||78,30,84)/100+1e-9)return {ok:false,reason:'POSITION_MARGIN_TOO_LARGE',qty,initialMarginUsd:initialMargin,marginCapPct,capitalBaseUsd:capital};
  return {ok:true,qty,notionalUsd:notional,actualRiskUsd:actualRisk,initialMarginUsd:initialMargin,leverage,capitalBaseUsd:capital};
}

export function addTranche(state={},x={}){
  const tranches=Array.isArray(state.tranches)?[...state.tranches]:[],id=String(x.id||`BTC-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`),row={id,symbol:'BTCUSDT',status:'OPEN',createdAt:Date.now(),managedSl:x.sl,protected:false,...x,id};tranches.push(row);return {...state,tranches,highWaterUsd:Math.max(num(state.highWaterUsd),num(x.equityUsd)),lastTrancheId:id};
}
export function updateTrancheProtection(state={},id,managedSl){const tranches=(state.tranches||[]).map(t=>{if(String(t.id)!==String(id))return t;const protectedNow=String(t.side)==='Buy'?num(managedSl)>=num(t.entry):num(managedSl)<=num(t.entry);return {...t,managedSl:num(managedSl),protected:protectedNow||t.protected};});return {...state,tranches};}
export function closeAllTranches(state={},meta={}){return {...state,tranches:(state.tranches||[]).map(t=>String(t.status||'OPEN')==='OPEN'?{...t,status:'CLOSED',closedAt:Date.now(),...meta}:t)};}

export const BTC_RISK_ENGINE_VERSION='BTC_RISK_RECYCLE_V4_BALANCE_EQUITY_CAPITAL';
