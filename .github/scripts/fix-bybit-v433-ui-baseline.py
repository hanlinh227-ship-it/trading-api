from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CF=ROOT/'cloudflare-worker'

def rep(p,a,b,n=1):
    p=Path(p); s=p.read_text(encoding='utf-8'); got=s.count(a)
    if got!=n: raise SystemExit(f'{p}: expected {n}, got {got}: {a[:140]}')
    p.write_text(s.replace(a,b),encoding='utf-8')

control=CF/'bybit-control-plane.js'
rep(control,
"import {BYBIT_UI_SCHEMA_VERSION,BYBIT_UI_ROUTES,BYBIT_UI_CAPABILITIES} from './bybit-ui-contract.js';",
"import {BYBIT_UI_SCHEMA_VERSION,BYBIT_UI_CORE_BASELINE,BYBIT_UI_ROUTES,BYBIT_UI_CAPABILITIES} from './bybit-ui-contract.js';")
rep(control,
"return {ok:true,readOnly:true,schemaVersion:BYBIT_UI_SCHEMA_VERSION,version:BYBIT_AUTO_VERSION,runtimeContract:BYBIT_RUNTIME_CONTRACT.version,routes:",
"return {ok:true,readOnly:true,schemaVersion:BYBIT_UI_SCHEMA_VERSION,coreBaseline:BYBIT_UI_CORE_BASELINE,version:BYBIT_AUTO_VERSION,runtimeContract:BYBIT_RUNTIME_CONTRACT.version,routes:")
rep(control,
"return {ok:true,readOnly:true,schemaVersion:BYBIT_UI_SCHEMA_VERSION,version:BYBIT_AUTO_VERSION,runtimeContract:BYBIT_RUNTIME_CONTRACT.version,runtimeRevision:",
"return {ok:true,readOnly:true,schemaVersion:BYBIT_UI_SCHEMA_VERSION,coreBaseline:BYBIT_UI_CORE_BASELINE,version:BYBIT_AUTO_VERSION,runtimeContract:BYBIT_RUNTIME_CONTRACT.version,runtimeRevision:")

validator=CF/'validate-btc-hyperscale.mjs'
rep(validator,
"for(const x of ['BYBIT_TRADE_UNIVERSE','x-bybit-symbol','BYBIT_MULTI_ENTRY_INFRA_READY','BYBIT_UI_ROUTES.bootstrap','BYBIT_UI_ROUTES.snapshot','uiSnapshot'])",
"for(const x of ['BYBIT_TRADE_UNIVERSE','x-bybit-symbol','BYBIT_MULTI_ENTRY_INFRA_READY','BYBIT_UI_CORE_BASELINE','BYBIT_UI_ROUTES.bootstrap','BYBIT_UI_ROUTES.snapshot','uiSnapshot'])")

handoff=ROOT/'BYBIT_UI_HANDOFF_V432.md'
s=handoff.read_text(encoding='utf-8')
if 'UI bootstrap and snapshot both expose `coreBaseline`' not in s:
    s += "- UI bootstrap and snapshot both expose `coreBaseline` so the frontend can reject an incompatible backend before rendering live data.\n"
handoff.write_text(s,encoding='utf-8')
print('BYBIT_V433_UI_BASELINE_PATCH_APPLIED')
