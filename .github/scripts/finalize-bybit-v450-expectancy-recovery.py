from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RISK=ROOT/'cloudflare-worker/bybit-btc-risk-engine.js'
p=RISK.read_text()
old="positionPeakR:0,invalidationCount:0,currentPositionMarginUsd:0,currentPositionLeverage:0,openPlans:{}};"
new="positionPeakR:0,invalidationCount:0,hardInvalidationCount:0,profitHarvestWeakCount:0,earlyProfitHarvestWeakCount:0,profitFloorHit:false,profitFloorHitAt:null,profitFloorPeakNetUsd:0,currentPositionMarginUsd:0,currentPositionLeverage:0,openPlans:{}};"
if old not in p:raise SystemExit('MISSING_MARKER:flat_state_reset')
RISK.write_text(p.replace(old,new,1))
print('BYBIT_V450_FINAL_STATE_RESET_APPLIED')
