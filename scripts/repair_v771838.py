from pathlib import Path

ROOT = Path('.')

def patch(path, replacements, required=()):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    original = s
    for old, new in replacements:
        if old not in s:
            raise SystemExit(f'{path}: missing expected text: {old[:120]}')
        s = s.replace(old, new)
    for token in required:
        if token not in s:
            raise SystemExit(f'{path}: required token missing after patch: {token}')
    if s != original:
        p.write_text(s, encoding='utf-8')
        print('patched', path)
    else:
        print('unchanged', path)

patch('cloudflare-worker/adaptive-tuning.js', [
    ('version:"V77.18.37"', 'version:"V77.18.38"'),
    ('out.version="V77.18.37"', 'out.version="V77.18.38"'),
    ('state={version:"V77.18.37"', 'state={version:"V77.18.38"'),
    ('version:"V77.18.37"}:{version:"V77.18.37"', 'version:"V77.18.38"}:{version:"V77.18.38"'),
], required=('marketEntryBalanced:true','forexMinRR:1.15','bMicroMin:.50'))

patch('cloudflare-worker/engine-v77168.js', [
    ('version: "V77.16.17",', 'version: "V77.16.18",'),
    ('service: "Trading V77.16.17 Market Isolation + Forex R4",', 'service: "Trading V77.16.18 Balanced Market Routing R5",'),
], required=('MARKET_SIGNAL','FX_SESSION_CONTINUATION_ZONE','strengthNormalizedSigned','INDEX_CASH'))

patch('cloudflare-worker/index.js', [
    ('const VERSION="V77.18.36",SERVICE="Trading V77.18.36 Market Isolation + Forex R4";', 'const VERSION="V77.18.38",SERVICE="Trading V77.18.38 Repair + Deploy Sync";'),
    ('const RELEASE_NAME="Market Isolation + Forex R4";', 'const RELEASE_NAME="Repair + Deploy Sync";'),
], required=('ensureDualAiIntervention','HYRO • VỊ THẾ LIVE'))

patch('cloudflare-worker/hub-v77171.js', [
    ('const VERSION="V77.18.36",UI_REV="HUB-R7-MARKET-ISOLATED",SERVICE="Trading V77.18.36 • Market Isolated UX";', 'const VERSION="V77.18.38",UI_REV="HUB-R8-BALANCED",SERVICE="Trading V77.18.38 • Balanced Market UX";'),
], required=('market:forex','market:crypto','market:metal','market:index','/books?group='))

patch('cloudflare-worker/dual-ai-intervention.js', [
    ('const REVIEW_REV="FOREX_MARKET_ISOLATION_R4";', 'const REVIEW_REV="MARKET_BALANCE_R5_BUDGET";'),
    ('max_tokens:2400', 'max_tokens:1400'),
    ('Perform FOREX_MARKET_ISOLATION_R4 first.', 'Perform MARKET_BALANCE_R5_BUDGET first. Spend tokens only on high-impact duplicated gates, MARKET-vs-LIMIT imbalance, Forex opportunity suppression, Hyro A/B market routing, and deployment/runtime consistency.'),
    ('lastAction:"FOREX_MARKET_ISOLATION_R4"', 'lastAction:"MARKET_BALANCE_R5_BUDGET"'),
    ('🧠 CLAUDE • METAL + INDEX CASH', '🧠 CLAUDE • MARKET BALANCE R5'),
], required=('MARKET_BALANCE_R5_BUDGET','max_tokens:1400','hardPropLimits:true'))

p = ROOT / '.github/workflows/validate-cloudflare-v77.yml'
s = p.read_text(encoding='utf-8')
s = s.replace("locks(engine,['V77.16.17','Market Isolation + Forex R4'", "locks(engine,['V77.16.18','Balanced Market Routing R5'")
s = s.replace("locks(index,['V77.18.36','Market Isolation + Forex R4'", "locks(index,['V77.18.38','Repair + Deploy Sync'")
s = s.replace("locks(hub,['V77.18.36','HUB-R7-MARKET-ISOLATED'", "locks(hub,['V77.18.38','HUB-R8-BALANCED'")
s = s.replace("locks(dual,['FOREX_MARKET_ISOLATION_R4','fresh explicit analysis quote','MARKET-ISOLATED HUB']", "locks(dual,['MARKET_BALANCE_R5_BUDGET','max_tokens:1400','fresh explicit analysis quote','MARKET-ISOLATED HUB']")
s = s.replace("locks(adaptive,['hardNews:true'", "locks(adaptive,['V77.18.38','marketEntryBalanced:true','hardNews:true'")
s = s.replace("console.log('V77.18.36 Market Isolation + Forex R4 validation PASS');", "console.log('V77.18.38 Repair + Deploy Sync validation PASS');")
for token in ('V77.16.18','V77.18.38','HUB-R8-BALANCED','MARKET_BALANCE_R5_BUDGET','max_tokens:1400'):
    if token not in s:
        raise SystemExit(f'validator missing {token}')
p.write_text(s, encoding='utf-8')
print('patched .github/workflows/validate-cloudflare-v77.yml')

print('V77.18.38_REPAIR_PATCH_OK')
