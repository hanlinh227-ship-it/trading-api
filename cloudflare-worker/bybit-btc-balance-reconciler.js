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
  const type=String(row.type||'').toUpperCase();
  if(type!=='TRANSFER_IN'&&type!=='TRANSFER_OUT')return null;
  const raw=num(row.cashFlow||row.change),amount=Math.abs(raw);
  if(!(amount>0))return null;
  const direction=type==='TRANSFER_IN'?1:-1;
  return {id:String(row.id||`${row.transactionTime}:${type}:${amount}`),type,amountUsd:amount,signedUsd:direction*amount,at:num(row.transactionTime),cashBalanceUsd:num(row.cashBalance)};
}

export async function reconcileBtcAccountBalance(env){
  const api=bybitV5(env),now=Date.now(),[wallet,state0]=await Promise.all([api.wallet(),get(env)]),snap=walletSnapshot(wallet),state={...state0};
  if(!(snap.equityUsd>0))return {ok:false,reason:'BALANCE_EQUITY_INVALID',snapshot:snap,state};

  const previousScan=num(state.cashFlowScanAt)||0,startTime=Math.max(now-7*DAY,previousScan>0?previousScan-5*60000:now-DAY);
  let tx={result:{list:[]}};
  try{tx=await api.signed('GET','/v5/account/transaction-log',{accountType:'UNIFIED',currency:'USDT',startTime,endTime:now,limit:50});}catch(e){
    state.lastBalanceReconcileError={at:iso(),error:String(e?.message||e).slice(0,240)};
    state.lastWalletBalanceUsd=snap.walletBalanceUsd;state.lastEquityUsd=snap.equityUsd;state.lastAvailableUsd=snap.availableUsd;state.lastBalanceObservedAt=iso();
    await put(env,state);return {ok:true,reason:'WALLET_UPDATED_TRANSACTION_LOG_UNAVAILABLE',snapshot:snap,state,error:state.lastBalanceReconcileError};
  }

  const seen=new Set((state.cashFlowSeenIds||[]).map(String)),events=[];
  for(const row of tx?.result?.list||[]){const e=classifyTransfer(row);if(!e||seen.has(e.id))continue;if(previousScan>0&&e.at>0&&e.at<previousScan-5*60000)continue;events.push(e);seen.add(e.id);}
  events.sort((a,b)=>a.at-b.at);
  const netExternalCashFlowUsd=events.reduce((s,x)=>s+x.signedUsd,0);

  const oldHigh=num(state.highWaterUsd)||snap.equityUsd;
  const oldProtected=num(state.protectedEquityUsd);
  if(Math.abs(netExternalCashFlowUsd)>1e-12){
    state.highWaterUsd=Math.max(0,oldHigh+netExternalCashFlowUsd);
    if(oldProtected>0)state.protectedEquityUsd=Math.max(0,oldProtected+netExternalCashFlowUsd);
    state.lastExternalCashFlow={at:iso(),netUsd:netExternalCashFlowUsd,events};
    state.cumulativeExternalCashFlowUsd=num(state.cumulativeExternalCashFlowUsd)+netExternalCashFlowUsd;
  }else if(!(state.highWaterUsd>0))state.highWaterUsd=snap.equityUsd;

  state.lastWalletBalanceUsd=snap.walletBalanceUsd;
  state.lastEquityUsd=snap.equityUsd;
  state.lastAvailableUsd=snap.availableUsd;
  state.lastUnrealisedPnlUsd=snap.unrealisedPnlUsd;
  state.lastCumRealisedPnlUsd=snap.cumRealisedPnlUsd;
  state.cashFlowScanAt=now;
  state.cashFlowSeenIds=[...seen].slice(-250);
  state.lastBalanceObservedAt=iso();
  state.balanceAuthority='BYBIT_WALLET_PLUS_TRANSACTION_LOG';
  state.depositWithdrawalAware=true;
  await put(env,state);
  return {ok:true,reason:events.length?'EXTERNAL_CASHFLOW_RECONCILED':'BALANCE_RECONCILED',snapshot:snap,netExternalCashFlowUsd,events,state};
}

export const BTC_BALANCE_RECONCILER_VERSION='BTC_BALANCE_RECONCILER_V1';
