// Guards the architecture decision that the Exness market-data path is cloud-only: it must not
// depend on a local PC, MT5/MetaTrader, an Expert Advisor, a local tunnel or a bridge process, and
// it must stay read-only (GET) and pinned to Exness hosts.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isApprovedExnessHost} from './exness-market-data.js';

const FILES=['exness-market-data.js','exness-market-data-handler.js','exness-market-data-state.js','exness-tick-hub.js','exness-live-page.js'];
const ALLOWED_IMPORTS=new Set(['node:buffer','node:crypto','./exness-market-data.js','./exness-market-data-state.js','./exness-tick-hub.js','./exness-live-page.js','./worker-auth.js']);
const LOCAL_DEPENDENCY=/mt5|metatrader|\.ex5|expert advisor|localhost|127\.0\.0\.1|0\.0\.0\.0|\btunnel\b|ngrok|cloudflared|trycloudflare|\bvps\b|\bbridge\b/i;

for(const file of FILES){
  const source=readFileSync(new URL('./'+file,import.meta.url),'utf8');
  for(const match of source.matchAll(/^import[^'"]*['"]([^'"]+)['"]/gm))assert.ok(ALLOWED_IMPORTS.has(match[1]),file+' imports outside the cloud-only allowlist: '+match[1]);
  assert.doesNotMatch(source,LOCAL_DEPENDENCY,file+' must not reference a local/MT5/tunnel/bridge dependency');
  for(const match of source.matchAll(/\benv\.([A-Z0-9_]+)/g))assert.match(match[1],/^EXNESS_/,file+' reads a non-Exness environment variable: '+match[1]);
  assert.doesNotMatch(source,/method:\s*['"](?:POST|PUT|PATCH|DELETE)['"]/,file+' must not send a mutating HTTP method');
  assert.doesNotMatch(source,/\/(?:order|orders|trade|trades|position|positions|withdraw|deposit)\b/i,file+' must not reference a trading or funds route');
}

// Upstream hosts are limited to Exness itself; local and tunnel hosts are rejected.
for(const host of ['localhost','127.0.0.1','192.168.1.10','abc.ngrok.io','abc.trycloudflare.com','evil-exness.com','ap-x.exness.com.attacker.example'])assert.equal(isApprovedExnessHost(host),false,host+' must be rejected');
for(const host of ['api.exness.com','api.exness-api.com','ap-4decef67.exness.com','ap-qwerty123.trading.exness.com'])assert.equal(isApprovedExnessHost(host),true,host+' must be accepted');

console.log('Exness cloud-only isolation contract PASS');
