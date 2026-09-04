import {bybitV5} from './bybit-v5-client.js';

const KEY='bybit:btc:hyperscale:v2:state';
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const iso=()=>new Date().toISOString();
const DAY=86400000;

async function get(env){try{return await env.TRADING_STATE?.get(KEY,{type:'json'})||{};}catch{return {};}}
async function put(env,x){if(env.TRADING_STATE)await env.TRADING_STATE.put(KEY,JSON.stringify(x));}

function walletSnapshot(w={}){
  const a=w?.result?.list?.[0]||{},coin=(a.coin||[]).find(x=>String(x.coin)==='USDT')||{};
  const walletBalance=num(coin.walletBalance||a.totalWalletBalance),equity=num(a.totalEquity||coin.equity||walletBalance),available=num(a.totalAvailableBalance||coin.availableToWithdraw||coin.availableBalance);
  const unrealised=num(coin.unrealisedPnl||a.totalPerpUPL),cumRealised=num(coin.cumRealisedPnl);
  return {walletBalanceUsd:walletBalance,equityUsd:equity,availableUsd:available,unrealisedPnlUsd:unrealised,cumRealisedPnlUsd:cumRealised};
}

function classifyTransfer(row={}){
  const type=String(row.type||'').toUpperCase(),display=String(row.displayType||'').toUpperCase(),raw=num(row.cashFlow||row.change),amount=Math.abs(raw);
  if(!(amount>0))return null;
  let direction=0,kind=type;
  if(type==='TRANSFER_IN')direction=1;
  else if(type==='TRANSFER_OUT')direction=-1;
  else if(/DEPOSIT|TRANSFER_IN|CASH_IN/.test(display)){direction=1;kind=display||type||'DEPOSIT_LIKE';}
  else if(/WITHDRAW|TRANSFER_OUT|CASH_OUT/.test(display)){direction=-1;kind=display||type||'WITHDRAW_LIKE';}
  if(!direction)return null;
  return {id:String(row.id||`${row.transactionTime}:${kind}:${amount}`),type:kind,amountUsd:amount,signedUsd:direction*amount,at:num(row.transactionTime),cashBalanceUsd:num(row.cashBalance),source:'BYBIT_TRANSACTION_LOG'};
}

async function transactionRows(api,startTime,endTime){
  const out=[];let cursor='';
  for(let i=0;i<4;i++){
    const tx=await api.signed('GET','/v5/account/transaction-log',{accountType:'UNIFIED',currency:'USDT',startTime,endTime,limit:50,cursor});
    const result=tx?.result||{},rows=result.list||[];out.push(...rows);
    const next=String(result.nextPageCursor||'');if(!next||next===cursor)break;cursor=next;
  }
  const seen=new Set();return out.filter(x=>{const id=String(x?.id||`${x?.transactionTime}:${x?.type}:${x?.change}`);if(seen.has(id))return false;seen.add(id);return true;});
}

function inferredExternalCashFlow(state={},snap={}){
  const prevWallet=num(state.lastWalletBalanceUsd),prevReal=num(state.lastCumRealisedPnlUsd),nowWallet=num(snap.walletBalanceUsd),nowReal=num(snap.cumRealisedPnlUsd);
  if(!(prevWallet>0&&nowWallet>=0))return 0;
  const walletDelta=nowWallet-prevWallet,realisedDelta=nowReal-prevReal,residual=walletDelta-realisedDelta,threshold=Math.max(1,prevWallet*.05);
  return Math.abs(residual)>=threshold?residual:0;
}

function applySnapshot(state,snap,{externalCashFlowUsd=0}={}){
  const now=Date.now(),prevAt=Date.parse(state.lastBalanceObservedAt||'')||now,dt=Math.max(0,now-prevAt),halfLife=15*60*1000,alpha=dt<=0?1:1-Math.exp(-dt/halfLife),prevEq=num(state.smoothedEquityUsd)||snap.equityUsd,prevWallet=num(state.smoothedWalletBalanceUsd)||snap.walletBalanceUsd,external=Math.abs(num(externalCashFlowUsd))>1e-12;
  const smEq=external?snap.equityUsd:prevEq+(snap.equityUsd-prevEq)*alpha,smWallet=external?snap.walletBalanceUsd:prevWallet+(snap.walletBalanceUsd-prevWallet)*alpha,prevObserved=num(state.lastEquityUsd)||snap.equityUsd,hours=Math.max(dt/3600000,1/3600);
  state.smoothedEquityUsd=smEq;state.smoothedWalletBalanceUsd=smWallet;
  state.continuousCapitalUsd=Math.max(0,Math.min(snap.equityUsd,smEq,snap.walletBalanceUsd>0?Math.max(smWallet,snap.walletBalanceUsd*.75):smEq));
  state.lastContinuousCapitalUsd=state.continuousCapitalUsd;
  state.equityVelocityUsdPerHour=(snap.equityUsd-prevObserved)/hours;
  state.continuousScaleAuthority=external?'EXTERNAL_CASHFLOW_INSTANT_CAPITAL_REBASE':'TIME_DECAYED_EQUITY_BALANCE_INSTANT_DOWNSIDE';
  state.lastWalletBalanceUsd=snap.walletBalanceUsd;state.lastEquityUsd=snap.equityUsd;state.lastAvailableUsd=snap.availableUsd;state.lastUnrealisedPnlUsd=snap.unrealisedPnlUsd;state.lastCumRealisedPnlUsd=snap.cumRealisedPnlUsd;state.lastBalanceObservedAt=new Date(now).toISOString();
  state.balanceAuthority='BYBIT_WALLET_PLUS_TRANSACTION_LOG_PLUS_WALLET_DELTA_FALLBACK';state.depositWithdrawalAware=true;state.externalCashFlowInstantScale=true;return state;
}

export async function reconcileBtcAccountBalance(env){
  const api=bybitV5(env),now=Date.now(),[wallet,state0]=await Promise.all([api.wallet(),get(env)]),snap=walletSnapshot(wallet),state={...state0};
  if(!(snap.equityUsd>0))return {ok:false,reason:'BALANCE_EQUITY_INVALID',snapshot:snap,state};
  const previousScan=num(state.cashFlowScanAt)||0,startTime=Math.max(now-7*DAY,previousScan>0?previousScan-5*60000:now-DAY);
  let rows=[];try{rows=await transactionRows(api,startTime,now);}catch(e){state.lastBalanceReconcileError={at:iso(),error:String(e?.message||e).slice(0,240)};}
  const seen=new Set((state.cashFlowSeenIds||[]).map(String)),parsed=rows.map(classifyTransfer).filter(Boolean);
  if(previousScan<=0){for(const e of parsed)seen.add(e.id);applySnapshot(state,snap);state.highWaterUsd=snap.equityUsd;if(!(num(state.protectedEquityUsd)>0))state.protectedEquityUsd=snap.walletBalanceUsd;state.cashFlowScanAt=now;state.cashFlowSeenIds=[...seen].slice(-500);state.cumulativeExternalCashFlowUsd=num(state.cumulativeExternalCashFlowUsd);state.lastBalanceBaselineAt=iso();await put(env,state);return {ok:true,reason:'BALANCE_BASELINE_ESTABLISHED',snapshot:snap,netExternalCashFlowUsd:0,events:[],state};}
  const events=[];for(const e of parsed){if(seen.has(e.id))continue;if(e.at>0&&e.at<previousScan-5*60000)continue;events.push(e);seen.add(e.id);}events.sort((a,b)=>a.at-b.at);
  let netExternalCashFlowUsd=events.reduce((s,x)=>s+x.signedUsd,0),inferred=0;
  if(Math.abs(netExternalCashFlowUsd)<1e-12){inferred=inferredExternalCashFlow(state,snap);if(Math.abs(inferred)>1e-12){netExternalCashFlowUsd=inferred;events.push({id:`INFERRED-${now}-${Math.round(inferred*1e6)}`,type:inferred>0?'INFERRED_DEPOSIT':'INFERRED_WITHDRAWAL',amountUsd:Math.abs(inferred),signedUsd:inferred,at:now,cashBalanceUsd:snap.walletBalanceUsd,source:'WALLET_DELTA_MINUS_REALIZED_PNL'});}}
  const oldHigh=num(state.highWaterUsd)||snap.equityUsd,oldProtected=num(state.protectedEquityUsd);
  if(Math.abs(netExternalCashFlowUsd)>1e-12){state.highWaterUsd=Math.max(0,oldHigh+netExternalCashFlowUsd);if(oldProtected>0)state.protectedEquityUsd=Math.max(0,oldProtected+netExternalCashFlowUsd);state.lastExternalCashFlow={at:iso(),netUsd:netExternalCashFlowUsd,events};state.cumulativeExternalCashFlowUsd=num(state.cumulativeExternalCashFlowUsd)+netExternalCashFlowUsd;}else if(!(state.highWaterUsd>0))state.highWaterUsd=snap.equityUsd;
  applySnapshot(state,snap,{externalCashFlowUsd:netExternalCashFlowUsd});state.cashFlowScanAt=now;state.cashFlowSeenIds=[...seen].slice(-500);if(rows.length)state.lastBalanceReconcileError=null;await put(env,state);
  return {ok:true,reason:events.length?'EXTERNAL_CASHFLOW_RECONCILED':'BALANCE_RECONCILED',snapshot:snap,netExternalCashFlowUsd,events,inferredExternalCashFlowUsd:inferred,state};
}

export const BTC_BALANCE_RECONCILER_VERSION='BTC_BALANCE_RECONCILER_V4_INSTANT_EXTERNAL_CAPITAL_REBASE';
