#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.1.4 SECURITY OBSERVABILITY ==='
python3 - <<'PY'
from pathlib import Path
p=Path('src/safe-signal-export.js');s=p.read_text()
needle="holderEvidence:c.holderClusterAudit?.evidence||[]"
extra="holderEvidence:c.holderClusterAudit?.evidence||[],securityReviewReasons:c.securityReviewReasons||[],securityBlockReasons:c.securityBlockReasons||[],securityEvidence:c.securityEvidence||[],mintAuthorityDisabled:c.mintAuthorityDisabled,freezeAuthorityDisabled:c.freezeAuthorityDisabled,topHoldersPct:c.topHoldersPct??null,dexLiquidityUsd:c.dexLiquidityUsd??null,sellPriceImpactPct:c.sellPriceImpactPct??null,needsExtensionAudit:!!c.needsExtensionAudit"
if needle in s:s=s.replace(needle,extra,1)
elif 'securityReviewReasons:c.securityReviewReasons' not in s:raise SystemExit('EXPORT_NEEDLE_NOT_FOUND')
s=s.replace("version:'2.1.2'","version:'2.1.4'",1)
p.write_text(s)
PY
node --check src/safe-signal-export.js
chmod 664 src/safe-signal-export.js 2>/dev/null || true
sudo -n /bin/systemctl restart meme-alpha-paper.service
sleep 35
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
node --input-type=module - <<'NODE'
import fs from 'node:fs';const x=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/runtime-status/signal-snapshot.json','utf8'));console.log(`SIGNAL_VERSION=${x.version}`);for(const c of (x.candidates||[]).filter(c=>c.universeClass==='MEME_CONFIRMED').slice(0,15)){console.log(`MEME ${c.symbol} score=${c.score} sec=${c.securityDecision} token2022=${c.token2022} mintOff=${c.mintAuthorityDisabled} freezeOff=${c.freezeAuthorityDisabled} top=${c.topHoldersPct} dexLiq=${c.dexLiquidityUsd} sell=${c.sellRoute} sellImpact=${c.sellPriceImpactPct} review=${(c.securityReviewReasons||[]).join(';')||'-'} block=${(c.securityBlockReasons||[]).join(';')||'-'} holder=${c.holderAuditDecision||'-'} holderReview=${(c.holderReviewReasons||[]).join(';')||'-'}`)}if(x.version!=='2.1.4')throw new Error('VERSION');if(x.sourceHealth?.status!=='HEALTHY')throw new Error('SOURCE');console.log('V214_SECURITY_OBSERVABILITY_PASS');
NODE
echo LIVE_EXECUTION=FALSE
