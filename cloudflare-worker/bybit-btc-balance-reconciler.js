import {bybitV5} from './bybit-v5-client.js';

const KEY='bybit:capital:intelligence:v1';
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const iso=()=>new Date().toISOString();
const DAY=86400000;
const MIN_SHOCK_USD=.25;
const SHOCK_PCT=.005;
const UPSIDE_HALF_LIFE_MS=90_000;

async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:'json'})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}

function walletSnapshot(w={}){
  const a=w?.result?.list?.[0]||{},coin=(a.coin||[]).find(x=>String(x.coin)==='USDT')||{};
  const walletBalance=num(coin.walletBalance||a.totalWalletBalance),equity=num(a.totalEquity||coin.equity||walletBalance),available=num(a.totalAvailableBalance||coin.availableToWithdraw||coin.availableBalance);
  const unrealised=num(coin.unrealisedPnl||a.totalPerpUPL),cumRealised=num(coin.cumRealisedPnl);
  return {walletBalanceUsd:walletBalance,equityUsd:equity,availableUsd:available,unrealisedPnlUsd:unrealised,cumRealisedPnlUsd:cumRealised};
}
function transferDirection(type=''){
  const t=String(type||'').toUpperCase();
  if(t==='TRANSFER_IN'||t.endsWith('_TRANSFER_IN')||t.includes('TRANSFER_IN_')||t==='DBS_CASH_IN')return 1;
  if(t==='TRANSFER_OUT'||t.endsWith('_TRANSFER_OUT')||t.includes('TRANSFER_OUT_')||t==='DBS_CASH_OUT')return -1;
  return 0;
}
function classifyTransfer(row={}){
  const type=String(row.type||'').toUpperCase(),direction=transferDirection(type);if(!direction)return null;
  const raw=num(row.cashFlow||row.change),amount=Math.abs(raw);if(!(amount>0))return null;
  return {id:String(row.id||`${row.transactionTime}:${type}:${amount}`),type,amountUsd:amount,signedUsd:direction*amount,at:num(row.transactionTime),cashBalanceUsd:num(row.cashBalance),displayType:String(row.displayType||'')};
}
async function transactionPages(api,startTime,endTime){
  const rows=[];let cursor='';let pages=0;
  for(let i=0;i<8;i++){
    const q={accountType:'UNIFIED',currency:'USDT',startTime,endTime,limit:50};if(cursor)q.cursor=cursor;
    const x=await api.signed('GET','/v5/account/transaction-log',q),r=x?.result||{},list=Array.isArray(r.list)?r.list:[];rows.push(...list);pages++;
    const next=String(r.nextPageCursor||'');if(!next||next===cursor)break;cursor=next;
  }
  return {rows,pages};
}
function applySnapshot(state,snap,{forceUpside=false,reason='NORMAL'}={}){
  const now=Date.now(),prevAt=Date.parse(state.lastBalanceObservedAt||'')||now,dt=Math.max(0,now-prevAt),alpha=dt<=0?1:1-Math.exp(-dt/UPSIDE_HALF_LIFE_MS),prevEq=num(state.smoothedEquityUsd)||snap.equityUsd,prevWallet=num(state.smoothedWalletBalanceUsd)||snap.walletBalanceUsd,prevObserved=num(state.lastEquityUsd)||snap.equityUsd,prevWalletObserved=num(state.lastWalletBalanceUsd)||snap.walletBalanceUsd,prevAvailable=num(state.lastAvailableUsd)||snap.availableUsd,hours=Math.max(dt/3600000,1/3600),walletDelta=snap.walletBalanceUsd-prevWalletObserved,equityDelta=snap.equityUsd-prevObserved,availableDelta=snap.availableUsd-prevAvailable,threshold=Math.max(MIN_SHOCK_USD,Math.abs(prevWalletObserved)*SHOCK_PCT),positiveShock=forceUpside||walletDelta>=threshold,negativeShock=walletDelta<=-threshold||equityDelta<=-threshold;
  let smEq=prevEq+(snap.equityUsd-prevEq)*alpha,smWallet=prevWallet+(snap.walletBalanceUsd-prevWallet)*alpha;
  const hardCapital=Math.max(0,Math.min(snap.equityUsd,snap.walletBalanceUsd>0?snap.walletBalanceUsd:snap.equityUsd));
  let continuous;
  if(positiveShock){smEq=snap.equityUsd;smWallet=snap.walletBalanceUsd;continuous=hardCapital;}
  else if(negativeShock){continuous=hardCapital;}
  else continuous=Math.max(0,Math.min(snap.equityUsd,smEq,snap.walletBalanceUsd>0?Math.max(smWallet,snap.walletBalanceUsd*.90):smEq));
  state.smoothedEquityUsd=smEq;state.smoothedWalletBalanceUsd=smWallet;state.continuousCapitalUsd=continuous;state.equityVelocityUsdPerHour=(snap.equityUsd-prevObserved)/hours;
  state.capitalRecognition={at:new Date(now).toISOString(),reason,positiveShock,negativeShock,forceUpside,walletDeltaUsd:walletDelta,equityDeltaUsd:equityDelta,availableDeltaUsd:availableDelta,shockThresholdUsd:threshold,continuousCapitalUsd:continuous,hardCapitalUsd:hardCapital,lagUsd:Math.max(0,hardCapital-continuous)};
  state.continuousScaleAuthority='CAPITAL_INTELLIGENCE_V4_INSTANT_EXTERNAL_UPSIDE_INSTANT_DOWNSIDE_90S_ORGANIC_SMOOTH';
  state.lastWalletBalanceUsd=snap.walletBalanceUsd;state.lastEquityUsd=snap.equityUsd;state.lastAvailableUsd=snap.availableUsd;state.lastUnrealisedPnlUsd=snap.unrealisedPnlUsd;state.lastCumRealisedPnlUsd=snap.cumRealisedPnlUsd;state.lastBalanceObservedAt=new Date(now).toISOString();state.balanceAuthority='BYBIT_WALLET_PLUS_PAGINATED_TRANSACTION_LOG_SEPARATE_CAPITAL_STATE';state.depositWithdrawalAware=true;state.capitalStateVersion=4;return state;
}

export async function reconcileBtcAccountBalance(env){
  const api=bybitV5(env),now=Date.now(),[wallet,state0]=await Promise.all([api.wallet(),get(env)]),snap=walletSnapshot(wallet),state={...state0};
  if(!(snap.equityUsd>0))return {ok:false,reason:'BALANCE_EQUITY_INVALID',snapshot:snap,state};
  const previousScan=num(state.cashFlowScanAt)||0,startTime=Math.max(now-7*DAY,previousScan>0?previousScan-5*60000:now-DAY);
  let tx={rows:[],pages:0};
  try{tx=await transactionPages(api,startTime,now);}catch(e){
    state.lastBalanceReconcileError={at:iso(),error:String(e?.message||e).slice(0,240)};applySnapshot(state,snap,{reason:'TRANSACTION_LOG_UNAVAILABLE'});if(!(state.highWaterUsd>0))state.highWaterUsd=snap.equityUsd;await put(env,state);return {ok:true,reason:'WALLET_UPDATED_TRANSACTION_LOG_UNAVAILABLE',snapshot:snap,state,error:state.lastBalanceReconcileError};
  }
  const seen=new Set((state.cashFlowSeenIds||[]).map(String)),parsed=tx.rows.map(classifyTransfer).filter(Boolean);
  // V4 uses a dedicated capital state. First observation intentionally establishes a fresh
  // baseline from the live account, preventing legacy BTC symbol high-water from double-counting deposits.
  if(previousScan<=0){
    for(const e of parsed)seen.add(e.id);applySnapshot(state,snap,{forceUpside:true,reason:'V4_FRESH_CAPITAL_BASELINE'});state.highWaterUsd=snap.equityUsd;state.protectedEquityUsd=snap.walletBalanceUsd;state.cashFlowScanAt=now;state.cashFlowSeenIds=[...seen].slice(-1000);state.cumulativeExternalCashFlowUsd=0;state.lastBalanceBaselineAt=iso();state.migrationAuthority='FRESH_LIVE_ACCOUNT_BASELINE_SEPARATE_FROM_SYMBOL_STATE';state.transactionLogPages=tx.pages;state.transactionLogRows=tx.rows.length;state.lastBalanceReconcileError=null;await put(env,state);return {ok:true,reason:'CAPITAL_V4_BASELINE_ESTABLISHED',snapshot:snap,netExternalCashFlowUsd:0,events:[],state};
  }
  const events=[];for(const e of parsed){if(seen.has(e.id))continue;if(e.at>0&&e.at<previousScan-5*60000)continue;events.push(e);seen.add(e.id);}events.sort((a,b)=>a.at-b.at);const netExternalCashFlowUsd=events.reduce((s,x)=>s+x.signedUsd,0),oldHigh=num(state.highWaterUsd)||snap.equityUsd,oldProtected=num(state.protectedEquityUsd)||snap.walletBalanceUsd;
  if(Math.abs(netExternalCashFlowUsd)>1e-12){state.highWaterUsd=Math.max(0,oldHigh+netExternalCashFlowUsd);state.protectedEquityUsd=Math.max(0,oldProtected+netExternalCashFlowUsd);state.lastExternalCashFlow={at:iso(),netUsd:netExternalCashFlowUsd,events};state.cumulativeExternalCashFlowUsd=num(state.cumulativeExternalCashFlowUsd)+netExternalCashFlowUsd;}else if(!(state.highWaterUsd>0))state.highWaterUsd=snap.equityUsd;
  applySnapshot(state,snap,{forceUpside:netExternalCashFlowUsd>0,reason:events.length?'EXTERNAL_CASHFLOW_RECONCILED':'BALANCE_RECONCILED'});state.cashFlowScanAt=now;state.cashFlowSeenIds=[...seen].slice(-1000);state.transactionLogPages=tx.pages;state.transactionLogRows=tx.rows.length;state.lastBalanceReconcileError=null;await put(env,state);return {ok:true,reason:events.length?'EXTERNAL_CASHFLOW_RECONCILED':'BALANCE_RECONCILED',snapshot:snap,netExternalCashFlowUsd,events,state};
}
export const BTC_BALANCE_RECONCILER_VERSION='BTC_BALANCE_RECONCILER_V4_CAPITAL_INTELLIGENCE';
