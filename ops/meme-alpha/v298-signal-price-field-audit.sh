#!/usr/bin/env bash
set -euo pipefail
cd /opt/meme-alpha/app
node --input-type=module - <<'NODE'
import fs from 'node:fs';const s=JSON.parse(fs.readFileSync('runtime-status/signal-snapshot.json','utf8'));const c=(s.candidates||[])[0]||{};console.log('KEYS='+Object.keys(c).sort().join(','));for(const x of (s.candidates||[]).slice(0,5))console.log(JSON.stringify({symbol:x.symbol,mint:x.mint,priceUsd:x.priceUsd,price:x.price,markPriceUsd:x.markPriceUsd,liquidityUsd:x.liquidityUsd,priceChange5m:x.priceChange5m}));
NODE
echo V298_SIGNAL_PRICE_FIELD_AUDIT_PASS
