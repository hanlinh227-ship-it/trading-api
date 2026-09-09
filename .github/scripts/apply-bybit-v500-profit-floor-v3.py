from pathlib import Path

ROOT=Path('cloudflare-worker')

def patch(path, old, new, label):
    p=ROOT/path
    s=p.read_text()
    if old not in s:
        raise SystemExit(f'MISSING:{label}')
    p.write_text(s.replace(old,new,1))

# Raise the minimum planned NET profit per new scalp without increasing the risk budget.
patch('bybit-auto-config.js',
"authority:'SCALP_QUALITY_REALISTIC_TARGET_POSITIVE_NET_EDGE_FAST_TURNOVER',\n    // Hard entry floor is >$1 net at low scale. Larger profits come from runners, not by starving valid entries.\n    minPlannedNetProfitUsd:.30,\n    preferredRunnerNetProfitUsd:1.00,\n    minPlannedNetProfitPct:.35,\n    minViableNetProfitUsd:.18,\n    allowFloorRelaxationForFastScalp:true,\n    profitFloorLadder:[\n      {equityUsd:0,minNetUsd:.25},{equityUsd:50,minNetUsd:.35},{equityUsd:75,minNetUsd:.45},\n      {equityUsd:100,minNetUsd:.55},{equityUsd:150,minNetUsd:.75},{equityUsd:250,minNetUsd:1.10},\n      {equityUsd:500,minNetUsd:2.00},{equityUsd:1000,minNetUsd:3.50},{equityUsd:2500,minNetUsd:8.00},\n      {equityUsd:5000,minNetUsd:16.00},{equityUsd:10000,minNetUsd:32.00}\n    ],\n    profitFloorBufferMult:1.04,",
"authority:'SCALP_QUALITY_MIN_ONE_USD_NET_POSITIVE_EDGE_FAST_TURNOVER',\n    // New-risk admission requires at least $1 planned NET after estimated trading costs.\n    // Profit is increased through qualified sizing/leverage inside the existing risk cap; TP is never stretched beyond the scalp runner cap.\n    minPlannedNetProfitUsd:1.00,\n    preferredRunnerNetProfitUsd:1.50,\n    minPlannedNetProfitPct:1.00,\n    minViableNetProfitUsd:1.00,\n    allowFloorRelaxationForFastScalp:false,\n    profitFloorLadder:[\n      {equityUsd:0,minNetUsd:1.00},{equityUsd:50,minNetUsd:1.00},{equityUsd:75,minNetUsd:1.25},\n      {equityUsd:100,minNetUsd:1.50},{equityUsd:150,minNetUsd:2.00},{equityUsd:250,minNetUsd:3.00},\n      {equityUsd:500,minNetUsd:5.00},{equityUsd:1000,minNetUsd:9.00},{equityUsd:2500,minNetUsd:20.00},\n      {equityUsd:5000,minNetUsd:45.00},{equityUsd:10000,minNetUsd:90.00}\n    ],\n    profitFloorBufferMult:1.08,",
'profit floor config')

patch('bybit-auto-config.js',
"earlyHarvestMinNetUsd:.18,",
"earlyHarvestMinNetUsd:1.00,",
'early harvest one-dollar floor')

patch('bybit-runtime-contract.js',
"plannedNetProfitFloor:true,plannedNetProfitFloorStartsAtOneUsd:false,preferredRunnerNetProfitStartsAtOneUsd:true,continuousProfitFloorScale:true,",
"plannedNetProfitFloor:true,plannedNetProfitFloorStartsAtOneUsd:true,minimumNewEntryPlannedNetProfitUsd:1.00,profitFloorRelaxationDisabled:true,preferredRunnerNetProfitStartsAtOneUsd:true,continuousProfitFloorScale:true,",
'runtime profit floor contract')

patch('validate-btc-hyperscale.mjs',
"assert.equal(cfg.scalp.requireNetFloorAfterFees,true);assert.ok(cfg.scalp.minPlannedNetProfitUsd>=.25);assert.ok(cfg.scalp.preferredRunnerNetProfitUsd>=1);assert.equal(cfg.scalp.positiveAntiSweep.enabled,true);",
"assert.equal(cfg.scalp.requireNetFloorAfterFees,true);assert.ok(cfg.scalp.minPlannedNetProfitUsd>=1);assert.ok(cfg.scalp.minViableNetProfitUsd>=1);assert.ok(cfg.scalp.preferredRunnerNetProfitUsd>=1.5);assert.ok(cfg.scalp.minPlannedNetProfitPct>=1);assert.equal(cfg.scalp.allowFloorRelaxationForFastScalp,false);assert.ok(cfg.positionControl.earlyHarvestMinNetUsd>=1);assert.equal(cfg.scalp.positiveAntiSweep.enabled,true);",
'validator profit floor')

patch('validate-btc-hyperscale.mjs',
"assert.equal(BYBIT_RUNTIME_CONTRACT.recoveryMartingale,false);assert.equal(BYBIT_RUNTIME_CONTRACT.recoveryAddToLoser,false);assert.equal(BYBIT_RUNTIME_CONTRACT.opportunityBreadthDoesNotIncreaseRiskBudget,true);",
"assert.equal(BYBIT_RUNTIME_CONTRACT.recoveryMartingale,false);assert.equal(BYBIT_RUNTIME_CONTRACT.recoveryAddToLoser,false);assert.equal(BYBIT_RUNTIME_CONTRACT.opportunityBreadthDoesNotIncreaseRiskBudget,true);assert.equal(BYBIT_RUNTIME_CONTRACT.plannedNetProfitFloorStartsAtOneUsd,true);assert.equal(BYBIT_RUNTIME_CONTRACT.profitFloorRelaxationDisabled,true);assert.ok(Number(BYBIT_RUNTIME_CONTRACT.minimumNewEntryPlannedNetProfitUsd)>=1);",
'validator runtime floor')

print('BYBIT_V500_MIN_ONE_USD_NET_FLOOR_PATCH_APPLIED')
