import {buildBtcMarketEvidence} from "./bybit-btc-market-model.js";
import {chooseBtcSetup,pyramidPermission} from "./bybit-btc-strategy-router.js";

export function evaluateBtcOpportunity(input={}){
  const evidence=buildBtcMarketEvidence(input);
  const setup=chooseBtcSetup({
    evidence,
    price:input.price,
    entryReference:input.entryReference,
    equityUsd:input.equityUsd,
    activeRiskUsd:input.activeRiskUsd,
    ddPct:input.ddPct
  });
  return {symbol:"BTCUSDT",evidence,setup};
}

export function evaluateBtcAdd(input={}){
  const evaluation=evaluateBtcOpportunity(input);
  const permission=pyramidPermission({
    priorTrancheProtected:Boolean(input.priorTrancheProtected),
    priorTrancheR:Number(input.priorTrancheR||0),
    newSetup:evaluation.setup,
    loser:Boolean(input.loser)
  });
  return {...evaluation,pyramid:permission};
}
