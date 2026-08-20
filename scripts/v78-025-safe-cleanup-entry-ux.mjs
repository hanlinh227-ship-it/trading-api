import fs from 'node:fs';
import {execFileSync} from 'node:child_process';

const providerPath='cloudflare-worker/providers/entry-intelligence.js';
const hubPath='cloudflare-worker/hub-v77171.js';
const expectedProvider='27860df6730d81092e47a536e7d2db9092c2c099';
const expectedHub='e4160944f299bbb5eade9b2a0d83a1e6f4ecdb4f';
const hash=p=>execFileSync('git',['hash-object',p],{encoding:'utf8'}).trim();
if(hash(providerPath)!==expectedProvider)throw new Error(`provider stale-write guard mismatch: ${hash(providerPath)}`);
if(hash(hubPath)!==expectedHub)throw new Error(`hub stale-write guard mismatch: ${hash(hubPath)}`);

function replaceOne(s,oldText,newText,label){const n=s.split(oldText).length-1;if(n!==1)throw new Error(`${label}: expected 1 occurrence, got ${n}`);return s.replace(oldText,newText);}

let provider=fs.readFileSync(providerPath,'utf8');
provider=replaceOne(
  provider,
  'if(market==="index")return {session:first(existingSession(a),c?.indexSession),instrumentIdentity:first(c?.instrumentIdentity,a?.instrumentType,"CASH_INDEX"),crossIndexConfirmation:first(c?.crossIndexConfirmation,c?.relativeStrength,a?.relativeStrength),riskContext:first(c?.riskSentiment,canon?.riskSentiment)};',
  'if(market==="index")return {session:first(existingSession(a),c?.indexSession),instrumentIdentity:first(c?.instrumentIdentity,a?.instrumentType),crossIndexConfirmation:first(c?.crossIndexConfirmation,c?.relativeStrength,a?.relativeStrength),riskContext:first(c?.riskSentiment,canon?.riskSentiment)};',
  'index_identity_fallback'
);
fs.writeFileSync(providerPath,provider);

let hub=fs.readFileSync(hubPath,'utf8');
hub=replaceOne(hub,'UI_REV="HUB-R13-ENTRY-INTEL-COVERAGE"','UI_REV="HUB-R14-ENTRY-INTEL-CLARITY"','ui_rev');
hub=replaceOne(hub,'🧭 ENTRY INTELLIGENCE • ACTIVE ADVISORY','🧭 ENTRY INTELLIGENCE • SIGNAL ADVISORY','intel_title');
hub=replaceOne(hub,'${pr.allowed===false?"⛔ BLOCK":"✅ ADMIT"}','${pr.allowed===false?"⛔ SIGNAL BLOCK":"✅ SIGNAL OK"}','intel_admission_label');
hub=replaceOne(hub,'📡 Freshness: ${x.quote?.freshness||"UNKNOWN"} • ${x.quote?.source||"—"}','📡 Giá: ${x.quote?.freshness||"UNKNOWN"} • ${x.quote?.source||"—"}','intel_freshness_label');
hub=replaceOne(hub,'🧩 Core evidence: ${c.known||0}/${c.total||0} • Market context: ${m.known||0}/${m.total||0}','🧩 Core: ${c.known||0}/${c.total||0} • Context: ${m.known||0}/${m.total||0}','intel_core_label');
hub=replaceOne(hub,'Ranking/admission advisory only • execution authority: NONE • Claude API không được gọi.','🎯 SIGNAL ONLY • không tự đặt lệnh • Claude API không được gọi.','intel_authority_label');
hub=replaceOne(hub,'async function entryCoverageText(env){const rows=await getEntryIntelligenceShadow(env,60);','async function entryCoverageText(env){const rows=await getEntryIntelligenceShadow(env,240);','coverage_window');
hub=replaceOne(hub,'const xs=rows.filter(x=>String(x?.market||"").toLowerCase()===market);','const xs=rows.filter(x=>String(x?.market||"").toLowerCase()===market).slice(0,60);','coverage_per_market_cap');
hub=replaceOne(hub,'`Mẫu gần nhất: ${rows.length}`','`Kho evidence: ${rows.length} • tối đa 60 mẫu/thị trường`','coverage_header');
hub=replaceOne(hub,'Read-only coverage • không đổi quyết định/lệnh.','Read-only coverage • SIGNAL ONLY • không đổi execution authority.','coverage_footer');
fs.writeFileSync(hubPath,hub);

const oneShots=[
  '.github/workflows/v78-020-entry-intelligence-batch.yml',
  '.github/workflows/v78-020-production-verify.yml',
  '.github/workflows/v78-021-apply.yml',
  '.github/workflows/v78-021-apply-v2.yml',
  '.github/workflows/v78-022-apply.yml',
  '.github/workflows/v78-022-fast.yml',
  '.github/workflows/v78-022-retry.yml',
  '.github/workflows/v78-023-hub-intelligence.yml',
  '.github/workflows/v78-024-doc-sync.yml',
  '.github/workflows/v78-025-safe-cleanup-entry-ux.yml'
];
for(const p of oneShots){
  let s=fs.readFileSync(p,'utf8');
  const m=s.match(/\non:\n[\s\S]*?\npermissions:/);
  if(!m)throw new Error(`${p}: on/permissions block not found`);
  s=s.replace(m[0],'\non:\n  workflow_dispatch:\n\npermissions:');
  fs.writeFileSync(p,s);
}
console.log('V78-025 applied: index identity fidelity, Hub clarity/balanced coverage, one-shot workflows manual-only');
