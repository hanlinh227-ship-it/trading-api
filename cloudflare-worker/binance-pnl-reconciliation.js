import {binanceUsdm} from "./binance-usdm-client.js";

function vnDayRange(nowMs=Date.now()){
  const offset=7*60*60*1000;
  const shifted=new Date(nowMs+offset);
  const y=shifted.getUTCFullYear(),m=shifted.getUTCMonth(),d=shifted.getUTCDate();
  const startUtc=Date.UTC(y,m,d,0,0,0)-offset;
  return {day:`${y}-${String(m+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`,startMs:startUtc,endMs:startUtc+86400000-1};
}

const num=v=>Number.isFinite(Number(v))?Number(v):0;

export async function reconcileDailyPnl(env,state={}){
  const api=binanceUsdm(env),range=vnDayRange();
  const income=await api.income({startTime:range.startMs,endTime:Math.min(range.endMs,Date.now()),limit:1000});
  const rows=Array.isArray(income)?income:[];
  let realized=0,commission=0,funding=0,other=0;
  const symbolNet={};
  for(const x of rows){
    const type=String(x.incomeType||""),v=num(x.income),symbol=String(x.symbol||"");
    if(type==="REALIZED_PNL")realized+=v;
    else if(type==="COMMISSION")commission+=v;
    else if(type==="FUNDING_FEE")funding+=v;
    else other+=v;
    if(symbol){symbolNet[symbol]=(symbolNet[symbol]||0)+v;}
  }
  const net=realized+commission+funding+other;
  const settled=Object.entries(symbolNet).filter(([,v])=>Math.abs(v)>1e-12).map(([symbol,v])=>({symbol,net:v})).sort((a,b)=>a.net-b.net);
  let lossStreak=0;
  for(let i=settled.length-1;i>=0;i--){if(settled[i].net<0)lossStreak++;else break;}
  return {
    day:range.day,
    source:"BINANCE_USDM_INCOME",
    realizedPnlUsd:realized,
    commissionUsd:commission,
    fundingUsd:funding,
    otherIncomeUsd:other,
    netPnlUsd:net,
    lossStreak,
    incomeRows:rows.length,
    reconciledAt:new Date().toISOString(),
    state:{...state,day:range.day,realizedUsd:net,lossStreak,lastPnlReconciledAt:new Date().toISOString()}
  };
}
