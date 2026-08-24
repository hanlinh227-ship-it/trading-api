export function dailyTargetPolicy(env,state={},equityUsd=0){
  const targetRaw=Number(env.BINANCE_DAILY_TARGET_USD||0);
  const targetUsd=Number.isFinite(targetRaw)&&targetRaw>0?targetRaw:0;
  const modeRaw=String(env.BINANCE_DAILY_TARGET_MODE||"HARD_ATTEMPT").toUpperCase();
  const mode=modeRaw==="FLEXIBLE"?"FLEXIBLE":"HARD_ATTEMPT";
  const realized=Number(state.realizedUsd||0);
  const remaining=Math.max(0,targetUsd-realized);
  const reached=targetUsd>0&&realized>=targetUsd;
  const pct=targetUsd>0?Math.max(0,Math.min(1,realized/targetUsd)):0;
  const equity=Number(equityUsd||0);
  const targetPct=equity>0&&targetUsd>0?targetUsd/equity*100:null;
  return {mode,targetUsd,realizedUsd:realized,remainingUsd:remaining,reached,progressPct:pct*100,targetPctOfEquity:targetPct,keepScanningUntilTarget:mode==="HARD_ATTEMPT"&&!reached,allowQualityRelaxation:false,forceTrade:false,forceRiskIncrease:false,stopReason:reached?"DAILY_TARGET_REACHED":null};
}
