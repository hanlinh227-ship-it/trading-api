from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CF=ROOT/'cloudflare-worker'

def rep(path, old, new, count=1):
    p=Path(path); s=p.read_text(encoding='utf-8'); got=s.count(old)
    if got!=count: raise SystemExit(f'{p}: expected {count}, got {got}: {old[:160]}')
    p.write_text(s.replace(old,new),encoding='utf-8')

controller=CF/'bybit-multi-asset-controller.js'
rep(controller,
"if(slotUsage(positions,equity)>=baseMax-1e-9)return 'PORTFOLIO_RISK_SLOT_CAP';if(groupSlotUsage(positions,p.correlationGroup,equity)>=correlationCapForEquity(equity)-1e-9)return 'PORTFOLIO_CORRELATION_RISK_SLOT_CAP';",
"const pendingEntrySlot=1;if(slotUsage(positions,equity)+pendingEntrySlot>baseMax+1e-9)return 'PORTFOLIO_RISK_SLOT_CAP';if(groupSlotUsage(positions,p.correlationGroup,equity)+pendingEntrySlot>correlationCapForEquity(equity)+1e-9)return 'PORTFOLIO_CORRELATION_RISK_SLOT_CAP';")
rep(controller,
"export const BYBIT_MULTI_ASSET_CONTROLLER_VERSION='BYBIT_MULTI_ASSET_CONTROLLER_V3_PROTECTED_RISK_SLOT_UI_READY';",
"export const BYBIT_MULTI_ASSET_CONTROLLER_VERSION='BYBIT_MULTI_ASSET_CONTROLLER_V3_1_PENDING_SLOT_GUARD_UI_READY';")

runtime=CF/'bybit-runtime-contract.js'
rep(runtime,"BYBIT_MULTI_ASSET_RUNTIME_V18_PROTECTED_RISK_SLOT_UI_READY","BYBIT_MULTI_ASSET_RUNTIME_V19_FINAL_CORE_FREEZE_UI_READY")
rep(runtime,"BYBIT-MULTI-STATEFLOW-4.3.2","BYBIT-MULTI-STATEFLOW-4.3.3")
rep(runtime,"portfolioAuthority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V1'","portfolioAuthority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V4_PROTECTED_RISK_SLOT_REUSE'")
rep(runtime,"scalpAuthority:'OBJECTIVE_SCALE_FLOOR_ADAPTIVE_LEVERAGE_THESIS_AWARE_RUNNER'","scalpAuthority:'OBJECTIVE_PROFIT_FLOOR_EDGE_PERSISTENCE_FLOOR_LOCK'")
rep(runtime,"protectedRiskSlotReuse:true,physicalPositionHardBuffer:true","protectedRiskSlotReuse:true,riskSlotAdmissionIncludesPendingEntry:true,physicalPositionHardBuffer:true")

config=CF/'bybit-auto-config.js'
rep(config,"BYBIT-MULTI-STATEFLOW-4.3.2 PROTECTED-RISK-SLOT + UI-READY","BYBIT-MULTI-STATEFLOW-4.3.3 FINAL-CORE-FREEZE + UI-READY")

ui=CF/'bybit-ui-contract.js'
rep(ui,"export const BYBIT_UI_SCHEMA_VERSION='BYBIT_UI_SCHEMA_V1';","export const BYBIT_UI_SCHEMA_VERSION='BYBIT_UI_SCHEMA_V1';\nexport const BYBIT_UI_CORE_BASELINE='BYBIT-MULTI-STATEFLOW-4.3.3';")
rep(ui,"  readOnlyBootstrap:true,","  coreBackendFrozenForUiV1:true,\n  readOnlyBootstrap:true,")

idx=CF/'index.js'
rep(idx,"import {BYBIT_UI_SCHEMA_VERSION,BYBIT_UI_ROUTES} from './bybit-ui-contract.js';","import {BYBIT_UI_SCHEMA_VERSION,BYBIT_UI_ROUTES,BYBIT_UI_CORE_BASELINE} from './bybit-ui-contract.js';")
rep(idx,"ui:{schemaVersion:BYBIT_UI_SCHEMA_VERSION,routes:BYBIT_UI_ROUTES,snapshotAuth:'ACTION_OR_VPS_BRIDGE_KEY'}","ui:{schemaVersion:BYBIT_UI_SCHEMA_VERSION,coreBaseline:BYBIT_UI_CORE_BASELINE,routes:BYBIT_UI_ROUTES,snapshotAuth:'ACTION_OR_VPS_BRIDGE_KEY'}")

handoff=ROOT/'BYBIT_UI_HANDOFF_V432.md'
s=handoff.read_text(encoding='utf-8')
s=s.replace('Bybit Bot V4.3.2 — UX/UI Handoff','Bybit Bot V4.3.3 — FINAL CORE FREEZE / UX/UI Handoff')
s=s.replace('`BYBIT-MULTI-STATEFLOW-4.3.2`','`BYBIT-MULTI-STATEFLOW-4.3.3`')
s=s.replace('`BYBIT_MULTI_ASSET_RUNTIME_V18_PROTECTED_RISK_SLOT_UI_READY`','`BYBIT_MULTI_ASSET_RUNTIME_V19_FINAL_CORE_FREEZE_UI_READY`')
s=s.replace('After the live position reaches its profit floor, V4.3.2 targets','After the live position reaches its profit floor, V4.3.3 targets')
s += "\n## Final core-freeze correction\n- Risk-slot admission now reserves the full pending slot before opening a new position. This prevents a new order from pushing weighted risk slots or correlation slots above their configured caps.\n- Runtime metadata now points to the actual V4 portfolio authority and floor-lock scalp authority.\n- `BYBIT_UI_SCHEMA_V1` remains stable for the UX/UI project.\n"
handoff.write_text(s,encoding='utf-8')

validator=CF/'validate-btc-hyperscale.mjs'
rep(validator,"BYBIT_MULTI_ASSET_CONTROLLER_V3_PROTECTED_RISK_SLOT_UI_READY","BYBIT_MULTI_ASSET_CONTROLLER_V3_1_PENDING_SLOT_GUARD_UI_READY")
rep(validator,"'PORTFOLIO_RISK_SLOT_CAP'","'PORTFOLIO_RISK_SLOT_CAP','pendingEntrySlot=1'")
rep(validator,"BYBIT_MULTI_ASSET_RUNTIME_V18_PROTECTED_RISK_SLOT_UI_READY","BYBIT_MULTI_ASSET_RUNTIME_V19_FINAL_CORE_FREEZE_UI_READY")
rep(validator,"BYBIT-MULTI-STATEFLOW-4.3.2","BYBIT-MULTI-STATEFLOW-4.3.3",2)
rep(validator,"'protectedRiskSlotReuse:true'","'protectedRiskSlotReuse:true','riskSlotAdmissionIncludesPendingEntry:true'")
rep(validator,"'BYBIT_UI_SCHEMA_V1'","'BYBIT_UI_SCHEMA_V1','coreBackendFrozenForUiV1:true'")

print('BYBIT_V433_FINAL_CORE_FREEZE_APPLIED')
