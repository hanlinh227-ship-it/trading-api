import {bybitExecutionMode} from './bybit-auto-config.js';
import {bybitV5,normalizeBybitFilter,roundTick} from './bybit-v5-client.js';
import {buildBybitDynamicUniverse} from './bybit-dynamic-universe.js';

const STATE_KEY='bybit:demo:smoke5:v1';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const on=v=>String(v||'').toLowerCase()==='true';

async function kvGet(env){try{return await env.TRADING_STATE?.get(STATE_KEY,{type:'json'})||{};}catch{return {};}}
async function kvPut(env,x){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(STATE_KEY,JSON.stringify(x));}catch{}}

function decimals(step){
  const s=String(step||'');
  if(s.includes('e-'))return Math.max(0,Number(s.split('e-')[1])||0);
  return s.includes('.')?s.split('.')[1].length:0;
}
function ceilStep(value,step){
  const st=num(step);if(!(st>0))return num(value);
  return Math.ceil((num(value)-1e-12)/st)*st;
}
function fmt(value,step){
  return Number(value).toFixed(Math.min(12,decimals(step))).replace(/\.?0+$/,'');
}
function openRows(raw={}){return (raw?.result?.list||[]).filter(x=>num(x.size)>0);}
function activeOrders(raw={}){return (raw?.result?.list||[]).filter(x=>!['Filled','Cancelled','Rejected','Deactivated'].includes(String(x.orderStatus||'')));}

function ensureDemo(env){
  const mode=bybitExecutionMode(env);
  if(mode!=='DEMO')throw new Error('DEMO_SMOKE_REQUIRES_DEMO_MODE');
  if(!on(env.BYBIT_AUTO_ENABLED))throw new Error('DEMO_SMOKE_REQUIRES_ENGINE_ENABLED');
  if(on(env.BYBIT_AUTO_LIVE))throw new Error('DEMO_SMOKE_LIVE_REQUEST_PRESENT');
  return mode;
}

async function accountSnapshot(api){
  const [w,p,o]=await Promise.all([api.wallet(),api.positions(),api.openOrders()]);
  const acct=w?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==='USDT')||{};
  return {
    account:{totalEquity:num(acct.totalEquity||coin.equity),walletBalance:num(acct.totalWalletBalance||coin.walletBalance),availableBalance:num(acct.totalAvailableBalance||coin.availableToWithdraw)},
    positions:openRows(p),
    openOrders:activeOrders(o),
  };
}

export async function openDemoSmoke5(env,{count=5,notionalUsd=10}={}){
  ensureDemo(env);
  const api=bybitV5(env),before=await accountSnapshot(api);
  if(before.positions.length||before.openOrders.length)throw new Error('DEMO_SMOKE_REQUIRES_FLAT_ACCOUNT');
  const universe=await buildBybitDynamicUniverse(env,api);
  const eligible=(universe.ranked||[]).filter(x=>x.eligible===true&&x.marketCapTop100===true);
  if(eligible.length<count)throw new Error('DEMO_SMOKE_NOT_ENOUGH_ELIGIBLE_SYMBOLS');
  const chosen=eligible.slice(0,Math.max(1,Math.min(5,Number(count)||5)));
  const instruments=await api.instruments(),instrumentMap=new Map((instruments?.result?.list||[]).map(x=>[String(x.symbol||''),normalizeBybitFilter(x)]));
  const opened=[],stamp=Date.now().toString(36);
  for(let i=0;i<chosen.length;i++){
    const row=chosen[i],symbol=String(row.symbol||''),filter=instrumentMap.get(symbol);
    if(!filter)throw new Error('DEMO_SMOKE_INSTRUMENT_MISSING:'+symbol);
    const price=num(row.last)||num((await api.ticker(symbol))?.result?.list?.[0]?.lastPrice);
    if(!(price>0))throw new Error('DEMO_SMOKE_PRICE_MISSING:'+symbol);
    const targetNotional=Math.max(Number(notionalUsd)||10,num(filter.minNotional)*1.25,5);
    const qtyRaw=Math.max(num(filter.minQty),targetNotional/price),qty=ceilStep(qtyRaw,filter.qtyStep);
    const qtyText=fmt(qty,filter.qtyStep),side=i%2===0?'Buy':'Sell',orderLinkId=('smk5-'+symbol+'-'+i+'-'+stamp).slice(0,36);
    try{await api.setLeverage(symbol,1);}catch{}
    const order=await api.signed('POST','/v5/order/create',{category:'linear',symbol,side,orderType:'Market',qty:qtyText,reduceOnly:false,orderLinkId});
    opened.push({symbol,side,qty:qtyText,orderId:String(order?.result?.orderId||''),orderLinkId,targetNotional});
    await sleep(250);
  }
  await sleep(1500);
  const live=openRows(await api.positions());
  for(const item of opened){
    const pos=live.find(x=>String(x.symbol)===item.symbol&&num(x.size)>0);
    if(!pos)continue;
    const filter=instrumentMap.get(item.symbol),entry=num(pos.avgPrice)||num(pos.markPrice);
    if(!(entry>0))continue;
    const sl=item.side==='Buy'?entry*.98:entry*1.02,tp=item.side==='Buy'?entry*1.02:entry*.98;
    try{
      await api.tradingStop({symbol:item.symbol,positionIdx:Number(pos.positionIdx||0),tpslMode:'Full',stopLoss:String(roundTick(sl,filter.tickSize)),takeProfit:String(roundTick(tp,filter.tickSize)),slTriggerBy:'MarkPrice',tpTriggerBy:'MarkPrice'});
      item.nativeProtection=true;
    }catch(e){item.nativeProtection=false;item.protectionError=String(e?.message||e).slice(0,180);}
  }
  const state={version:'BYBIT_DEMO_SMOKE_5X2M_V1',status:'OPEN',openedAt:Date.now(),holdMs:120000,count:opened.length,notionalUsd:Number(notionalUsd)||10,before:before.account,orders:opened,runtimeRevision:String(env.RUNTIME_REVISION||'UNKNOWN')};
  await kvPut(env,state);
  const after=await accountSnapshot(api);
  return {ok:true,demo:true,testOnly:true,forcedDiagnosticOrders:true,strategySignalBypassed:true,state,account:after.account,positions:after.positions.map(x=>({symbol:x.symbol,side:x.side,size:num(x.size),avgPrice:num(x.avgPrice),unrealisedPnl:num(x.unrealisedPnl),stopLoss:num(x.stopLoss),takeProfit:num(x.takeProfit)}))};
}

export async function closeDemoSmoke5(env){
  ensureDemo(env);
  const api=bybitV5(env),state=await kvGet(env);
  if(state?.status!=='OPEN'||!Array.isArray(state.orders))throw new Error('DEMO_SMOKE_NO_OPEN_TEST');
  const positions=openRows(await api.positions()),closed=[];
  for(const item of state.orders){
    const pos=positions.find(x=>String(x.symbol)===String(item.symbol)&&num(x.size)>0);
    if(!pos){closed.push({symbol:item.symbol,alreadyFlat:true});continue;}
    const closeSide=String(pos.side)==='Buy'?'Sell':'Buy',qty=String(pos.size);
    const orderLinkId=('smk5c-'+String(item.symbol)+'-'+Date.now().toString(36)).slice(0,36);
    const order=await api.signed('POST','/v5/order/create',{category:'linear',symbol:item.symbol,side:closeSide,orderType:'Market',qty,reduceOnly:true,orderLinkId});
    closed.push({symbol:item.symbol,side:closeSide,qty,orderId:String(order?.result?.orderId||'')});
    await sleep(250);
  }
  await sleep(1500);
  const after=await accountSnapshot(api),completed={...state,status:'CLOSED',closedAt:Date.now(),heldMs:Math.max(0,Date.now()-num(state.openedAt)),closed,before:state.before,after:after.account,equityDelta:num(after.account.totalEquity)-num(state.before?.totalEquity),walletDelta:num(after.account.walletBalance)-num(state.before?.walletBalance)};
  await kvPut(env,completed);
  return {ok:true,demo:true,testOnly:true,state:completed,positionsRemaining:after.positions.map(x=>({symbol:x.symbol,side:x.side,size:num(x.size)})),openOrdersRemaining:after.openOrders.length};
}

export async function getDemoSmoke5State(env){return kvGet(env);}
