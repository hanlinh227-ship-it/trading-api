from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def patch(rel,repls):
    p=ROOT/rel
    s=p.read_text()
    for old,new in repls:
        if old not in s:
            raise SystemExit(f'MISSING_PATTERN {rel}: {old[:120]}')
        s=s.replace(old,new)
    p.write_text(s)

patch('cloudflare-worker/bybit-coin-profiles.js',[
("deepScanCount:6,promotionScanCount:4,","deepScanCount:12,promotionScanCount:12,"),
("maxSpreadBps:7.5,minTurnoverUsd:35_000_000,runnerMaxR:4.2","maxSpreadBps:9.0,minTurnoverUsd:15_000_000,runnerMaxR:4.2"),
("authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V5_CONTINUOUS_RISK_SLOTS'","authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V6_BROAD_OPPORTUNITY_SAME_RISK_BUDGET'")
])

patch('cloudflare-worker/bybit-dynamic-universe.js',[
("const PROMOTION_EVIDENCE_TTL_MS=45*60*1000;","const PROMOTION_EVIDENCE_TTL_MS=35*60*1000;"),
("else if(turnover>=40_000_000&&spreadBps<=6.5&&(Math.abs(change)>=.008||oiValue>=20_000_000))","else if(turnover>=22_000_000&&spreadBps<=8.0&&(Math.abs(change)>=.007||oiValue>=10_000_000))"),
("else if(turnover>=75_000_000&&spreadBps<=5.5)","else if(turnover>=55_000_000&&spreadBps<=6.5)"),
("else if(turnover<12_000_000||spreadBps>10)","else if(turnover<6_000_000||spreadBps>12)"),
("turnover<12_000_000?'TURNOVER_TOO_LOW'","turnover<6_000_000?'TURNOVER_TOO_LOW'"),
("row.classification==='WATCH_READY'&&num(row.turnover)>=25_000_000&&num(row.spreadBps)<=7.5&&num(row.oiValue)>=8_000_000&&promotionPotential(row)>=.68","row.classification==='WATCH_READY'&&num(row.turnover)>=12_000_000&&num(row.spreadBps)<=9.0&&num(row.oiValue)>=4_000_000&&promotionPotential(row)>=.58"),
("hist.length>=4&&good>=3&&goodRatio>=.70&&fresh>=3&&freshRatio>=.75&&now-lastGoodAt<=20*60*1000","hist.length>=3&&good>=2&&goodRatio>=.67&&fresh>=3&&freshRatio>=.75&&now-lastGoodAt<=15*60*1000"),
("x.turnover>=8_000_000&&x.spreadBps<=9.5&&promotionPotential(x)>=.48","x.turnover>=4_000_000&&x.spreadBps<=11.5&&promotionPotential(x)>=.40"),
("BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION","BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V4_BROAD_OPPORTUNITY_PROMOTION")
])

patch('bybit-live-bridge/bybit_live_bridge.py',[
("MAX_WS_SYMBOLS=max(18,min(40,int(os.environ.get('BYBIT_MAX_WS_SYMBOLS','30'))))","MAX_WS_SYMBOLS=max(18,min(72,int(os.environ.get('BYBIT_MAX_WS_SYMBOLS','48'))))"),
("if turn>=35_000_000 and spread<=7.0:rows.append((turn,-spread,s))","if turn>=12_000_000 and spread<=9.5:rows.append((turn,-spread,s))"),
("EVENT_SYMBOL_LIMIT=max(4,min(12,int(os.environ.get('BYBIT_EVENT_SYMBOL_LIMIT','8'))))","EVENT_SYMBOL_LIMIT=max(4,min(24,int(os.environ.get('BYBIT_EVENT_SYMBOL_LIMIT','12'))))"),
("_default_events=list(CORE_SYMBOLS[:6])+_extra[:2]","_default_events=list(CORE_SYMBOLS[:8])+_extra[:4]")
])

patch('cloudflare-worker/bybit-runtime-contract.js',[
("BYBIT_MULTI_ASSET_RUNTIME_V23_REALIZED_EXPECTANCY_CAPITAL_PRESERVATION","BYBIT_MULTI_ASSET_RUNTIME_V24_BROAD_SCALP_OPPORTUNITY_NETWORK"),
("BYBIT-MULTI-STATEFLOW-4.5.0","BYBIT-MULTI-STATEFLOW-4.6.0"),
("universeAuthority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION'","universeAuthority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V4_BROAD_OPPORTUNITY_PROMOTION'"),
("capitalPreservationRecoveryMode:true,longRunCoreFreeze:true","capitalPreservationRecoveryMode:true,broadScalpUniverse:true,expandedWsCoverage:true,expandedDeepScan:true,expandedPromotionScan:true,opportunityBreadthDoesNotIncreaseRiskBudget:true,longRunCoreFreeze:true")
])

patch('cloudflare-worker/bybit-multi-asset-controller.js',[
("portfolioAuthority:BYBIT_PORTFOLIO_POLICY.authority,entrySelectionAuthority:'OBJECTIVE_SCAN_THEN_RANK_FRESH_RECHECK'","portfolioAuthority:BYBIT_PORTFOLIO_POLICY.authority,opportunityBreadthAuthority:'BROAD_CRYPTO_SCAN_SEPARATE_FROM_RISK_BUDGET',entrySelectionAuthority:'OBJECTIVE_SCAN_THEN_RANK_FRESH_RECHECK'")
])

patch('cloudflare-worker/validate-btc-hyperscale.mjs',[
("BYBIT-MULTI-STATEFLOW-4.5.0","BYBIT-MULTI-STATEFLOW-4.6.0"),
("BYBIT_MULTI_ASSET_RUNTIME_V23_REALIZED_EXPECTANCY_CAPITAL_PRESERVATION","BYBIT_MULTI_ASSET_RUNTIME_V24_BROAD_SCALP_OPPORTUNITY_NETWORK"),
("BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V3_DUAL_LANE_PROMOTION","BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V4_BROAD_OPPORTUNITY_PROMOTION"),
("assert.ok(BYBIT_PORTFOLIO_POLICY.promotionScanCount>=1);","assert.ok(BYBIT_PORTFOLIO_POLICY.deepScanCount>=12);assert.ok(BYBIT_PORTFOLIO_POLICY.promotionScanCount>=12);assert.equal(BYBIT_RUNTIME_CONTRACT.broadScalpUniverse,true);assert.equal(BYBIT_RUNTIME_CONTRACT.expandedWsCoverage,true);assert.equal(BYBIT_RUNTIME_CONTRACT.opportunityBreadthDoesNotIncreaseRiskBudget,true);"),
("persistentPromotionEvidence:true,cryptoOnlyDynamicUniverse:true","persistentPromotionEvidence:true,broadScalpUniverse:true,expandedWsCoverage:true,expandedDeepScan:true,expandedPromotionScan:true,cryptoOnlyDynamicUniverse:true")
])

print('BYBIT_V460_BROAD_SCALP_UNIVERSE_APPLIED')
