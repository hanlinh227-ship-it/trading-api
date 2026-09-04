import {BYBIT_BTC_ONLY_CONFIG,equityRiskUsd,canAllocateRisk} from "./bybit-btc-only-design.js";

const n=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));

export function chooseBtcSetup({evidence={},price=0,entryReference=0,equityUsd=0,activeRiskUsd=0,ddPct=0}={}){
  const regime=evidence?.regime?.regime||"TRANSITION",conf=n(evidence?.regime?.confidence),of=evidence?.orderflow||{},liq=evidence?.liquidity||{};
  let side=null,setupType=null,quality="BASE",score=0;

  if(regime==="TREND_UP"&&n(of.tradeDelta)>.10){side="Buy";setupType="TREND_PULLBACK_OR_CONTINUATION";score=68+conf*20;}
  else if(regime==="TREND_DOWN"&&n(of.tradeDelta)<-.10){side="Sell";setupType="TREND_PULLBACK_OR_CONTINUATION";score=68+conf*20;}
  else if(regime==="BREAKOUT_UP"&&n(of.tradeDelta)>.20){side="Buy";setupType="BREAKOUT_RETEST";score=72+conf*20;quality="STRONG";}
  else if(regime==="BREAKOUT_DOWN"&&n(of.tradeDelta)<-.20){side="Sell";setupType="BREAKOUT_RETEST";score=72+conf*20;quality="STRONG";}
  else if(regime==="RANGE"&&Math.abs(n(of.tradeDelta))<.35){
    // Range entries require an externally supplied reference zone. No blind mid-range trades.
    if(entryReference>0&&price>0){
      const drift=(price-entryReference)/entryReference;
      if(drift<=-.0015){side="Buy";setupType="RANGE_MEAN_REVERSION";score=66+conf*15;}
      else if(drift>=.0015){side="Sell";setupType="RANGE_MEAN_REVERSION";score=66+conf*15;}
    }
  }

  if(!side)return {ok:false,reason:"NO_EDGE",regime};
  if(regime==="HIGH_VOL_SHOCK"||regime==="TRANSITION"||regime==="SQUEEZE")return {ok:false,reason:"REGIME_NO_NEW_RISK",regime};

  if(Math.abs(n(of.imbalance))>.55&&Math.sign(n(of.imbalance))===Math.sign(side==="Buy"?1:-1))score+=4;
  if(n(liq.spreadBps)>8)score-=4;
  if(score>=90)quality="A_PLUS";else if(score>=82&&quality==="BASE")quality="STRONG";

  const candidateRiskUsd=equityRiskUsd({equityUsd,setupQuality:quality,ddPct});
  const budget=canAllocateRisk({equityUsd,activeRiskUsd,candidateRiskUsd,aPlus:quality==="A_PLUS",ddPct});
  if(!budget.ok)return {ok:false,reason:budget.reason,regime,score,candidateRiskUsd,budget};

  return {ok:true,side,setupType,quality,score:Math.round(score),candidateRiskUsd,budget,regime,executionPreference:setupType==="BREAKOUT_RETEST"?"IOC_OR_MARKET_IF_EDGE_SURVIVES_COST":"POST_ONLY_OR_LIMIT"};
}

export function pyramidPermission({priorTrancheProtected=false,priorTrancheR=0,newSetup,loser=false}={}){
  if(loser)return {ok:false,reason:"NO_ADD_TO_LOSER"};
  if(!priorTrancheProtected)return {ok:false,reason:"PRIOR_RISK_NOT_PROTECTED"};
  if(n(priorTrancheR)<.35)return {ok:false,reason:"INSUFFICIENT_WINNER_PROGRESS"};
  if(!newSetup?.ok)return {ok:false,reason:"NO_FRESH_EDGE"};
  return {ok:true,reason:"WINNER_PYRAMID_ALLOWED"};
}
