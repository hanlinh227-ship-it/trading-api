from pathlib import Path
R=Path(__file__).resolve().parents[2]

def patch(path,repls):
    p=R/path;s=p.read_text()
    for old,new in repls:
        if old not in s: raise SystemExit(f'MISSING {path}: {old[:100]}')
        s=s.replace(old,new,1)
    p.write_text(s)

patch('cloudflare-worker/bybit-auto-config.js',[
("{equityUsd:0,normal:11,strong:14,aPlus:18,max:20},\n      {equityUsd:50,normal:10,strong:13,aPlus:17,max:20},\n      {equityUsd:100,normal:9,strong:12,aPlus:16,max:18},\n      {equityUsd:250,normal:7.5,strong:10.5,aPlus:14,max:16},\n      {equityUsd:500,normal:6.5,strong:9.5,aPlus:12.5,max:14},",
 "{equityUsd:0,normal:14,strong:20,aPlus:28,max:35},\n      {equityUsd:50,normal:13,strong:19,aPlus:27,max:35},\n      {equityUsd:100,normal:12,strong:18,aPlus:25,max:32},\n      {equityUsd:250,normal:10,strong:15,aPlus:22,max:28},\n      {equityUsd:500,normal:8,strong:13,aPlus:19,max:24},"),
("baseEntryRiskPct:.70,strongEntryRiskPct:.95,aPlusEntryRiskPct:1.20,absoluteSingleEntryRiskPct:1.25,\n    maxActiveRiskPct:4.2,temporaryAPlusActiveRiskPct:5.0,maxPortfolioMarginPct:60,maxMarginPerPositionPct:55,minFreeReservePct:20,",
 "baseEntryRiskPct:1.15,strongEntryRiskPct:1.65,aPlusEntryRiskPct:2.35,absoluteSingleEntryRiskPct:2.50,\n    maxActiveRiskPct:7.0,temporaryAPlusActiveRiskPct:8.5,maxPortfolioMarginPct:72,maxMarginPerPositionPct:62,minFreeReservePct:15,"),
("addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,maxSameDirectionPositions:2,riskRecycleAfterProtection:true,",
 "addToLoser:false,pyramidWinner:true,martingale:false,gridRescue:false,dailyTarget:false,maxSameDirectionPositions:3,riskRecycleAfterProtection:true,"),
("{equityUsd:39,riskMult:1.00,marginCapPct:72},\n      {equityUsd:50,riskMult:1.06,marginCapPct:74},\n      {equityUsd:75,riskMult:1.12,marginCapPct:76},\n      {equityUsd:100,riskMult:1.18,marginCapPct:78},\n      {equityUsd:150,riskMult:1.24,marginCapPct:80},\n      {equityUsd:250,riskMult:1.30,marginCapPct:82},\n      {equityUsd:500,riskMult:1.36,marginCapPct:84}\n    ],maxRiskMult:1.40,maxMarginCapPct:84},",
 "{equityUsd:39,riskMult:1.00,marginCapPct:74},\n      {equityUsd:50,riskMult:1.08,marginCapPct:76},\n      {equityUsd:75,riskMult:1.16,marginCapPct:78},\n      {equityUsd:100,riskMult:1.24,marginCapPct:80},\n      {equityUsd:150,riskMult:1.32,marginCapPct:82},\n      {equityUsd:250,riskMult:1.40,marginCapPct:84},\n      {equityUsd:500,riskMult:1.48,marginCapPct:85}\n    ],maxRiskMult:1.55,maxMarginCapPct:85},"),
("drawdownGovernor:[{ddPct:2,multiplier:.88},{ddPct:4,multiplier:.75},{ddPct:7,multiplier:.60},{ddPct:10,multiplier:.45},{ddPct:15,multiplier:.25},{ddPct:20,multiplier:0}]",
 "drawdownGovernor:[{ddPct:3,multiplier:.92},{ddPct:5,multiplier:.80},{ddPct:8,multiplier:.65},{ddPct:12,multiplier:.45},{ddPct:16,multiplier:.25},{ddPct:20,multiplier:0}]")
])

patch('cloudflare-worker/bybit-coin-profiles.js',[
("authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V7_ALL_CRYPTO_SAME_RISK_BUDGET'","authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V8_CAPITAL_AWARE_FAST_SCALE'"),
("riskMult:.35,targetMult:1.02,stopMult:1.06","riskMult:.55,targetMult:1.08,stopMult:1.06"),
("leverageMult:.70,maxSpreadBps:20.0","leverageMult:.82,maxSpreadBps:20.0")
])

patch('cloudflare-worker/bybit-multi-asset-controller.js',[
("equityUsd:equity,continuousCapacityCapitalUsd:capacityCapital,walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd),lastCycleAt:iso(),",
 "equityUsd:equity,continuousCapacityCapitalUsd:capacityCapital,walletBalanceUsd:num(balance?.snapshot?.walletBalanceUsd),availableUsd:num(balance?.snapshot?.availableUsd),balanceReconcileReason:balance?.reason||null,externalCashFlowUsd:num(balance?.netExternalCashFlowUsd),lastExternalCashFlow:balance?.state?.lastExternalCashFlow||null,capitalScaleAuthority:balance?.state?.continuousScaleAuthority||null,lastCycleAt:iso(),")
])

patch('cloudflare-worker/bybit-runtime-contract.js',[
("export const BYBIT_RUNTIME_CONTRACT_VERSION='BYBIT_MULTI_ASSET_RUNTIME_V25_ALL_CRYPTO_SCALP_NETWORK';","export const BYBIT_RUNTIME_CONTRACT_VERSION='BYBIT_MULTI_ASSET_RUNTIME_V26_CAPITAL_AWARE_FAST_SCALE';"),
("export const BYBIT_AUTO_VERSION='BYBIT-MULTI-STATEFLOW-4.7.0';","export const BYBIT_AUTO_VERSION='BYBIT-MULTI-STATEFLOW-4.8.0';"),
("portfolioAuthority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V7_ALL_CRYPTO_SAME_RISK_BUDGET'","portfolioAuthority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V8_CAPITAL_AWARE_FAST_SCALE'"),
("continuousTimeCapitalScale:true,","continuousTimeCapitalScale:true,externalCashFlowInstantScale:true,depositWithdrawalAware:true,capitalRebaseDoesNotCountAsProfit:true,"),
("exchangeMaxLeverageCap:true,","exchangeMaxLeverageCap:true,riskBasedLeverageExpansion:true,leverageDoesNotOverrideStopRiskBudget:true,")
])
print('BYBIT_V480_CAPITAL_FAST_SCALE_PATCHED')
