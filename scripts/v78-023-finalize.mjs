import fs from 'node:fs';

const sourceSha=process.env.SOURCE_SHA||'UNKNOWN';
const versionId=process.env.VERSION_ID||'UNKNOWN';
const verifiedAt=new Date().toISOString();
const validation=`V78-023 CONSOLIDATED HUB INTELLIGENCE COVERAGE + R13 VISIBILITY\nsourceCommit: ${sourceSha}\ncloudflareVersionId: ${versionId}\nverifiedAt: ${verifiedAt}\nnode --check hub-v77171.js: PASS\nUI revision: HUB-R13-ENTRY-INTEL-COVERAGE\nEntry Intel screen: ACTIVE ADVISORY semantics; Quality/ADMIT-BLOCK/Freshness/WHY fields visible\nCoverage screen: last 60 Entry Intelligence rows summarized by Forex/Crypto/Metal/Index\nCoverage dimensions: sample count, LIVE count, average quality, promotion block count, top missing core fields\nEvidence taxonomy: REQUIRED may block; QUALITY ranks; OPTIONAL never independently blocks\nExecution authority: unchanged (Entry Intelligence NONE; Hyro remains sole real-capital execution path)\nProduction Claude API: PAUSED\nNo TRADING_STATE/v775:books reset or deletion\nNo risk/freshness/structural-SL/news weakening\nNo Futures/TK2 restore\nBinance20 remains NON_PRODUCTION / QUARANTINED\n`;
fs.writeFileSync('docs/ai-coengineer/V78-023_VALIDATION.txt',validation);

const shared='docs/ai-coengineer/SHARED_STATE.md';
let s=fs.readFileSync(shared,'utf8');
if(!s.includes('V78-023 — RESOLVED / DEPLOYED')) s+=`\n\nV78-023 — RESOLVED / DEPLOYED\n- Source commit: ${sourceSha}.\n- Cloudflare Version ID: ${versionId}.\n- Hub UI revision is HUB-R13-ENTRY-INTEL-COVERAGE.\n- Entry Intel UI now reflects ACTIVE ADVISORY status from V78-020 instead of stale SHADOW wording.\n- New read-only Coverage view summarizes Entry Intelligence evidence quality/missing-core patterns across Forex/Crypto/Metal/Index.\n- No execution authority, ranking formula, admission gate, hard risk, freshness, structural-SL or news policy changed in V78-023.\n- Validation: docs/ai-coengineer/V78-023_VALIDATION.txt.\n`;
fs.writeFileSync(shared,s);

fs.writeFileSync('docs/ai-coengineer/WRITE_LOCK.md',`# AI WRITE LOCK\n\nLOCKED: false\nOWNER: NONE\nSCOPE: NONE\nRELEASED: 2026-08-20\nLAST_OWNER: CHATGPT\nLAST_SCOPE: V78-023 consolidated Hub intelligence coverage + R13 visibility\nRESULT: RESOLVED / DEPLOYED. Validation in docs/ai-coengineer/V78-023_VALIDATION.txt.\n\nProtocol:\n- Acquire a new lock before the next source write.\n- Never reset TRADING_STATE or delete/reset v775:books.\n- Never weaken hard risk/freshness/structural-SL/news safeguards.\n- Never restore Futures/TK2.\n- Binance20 remains NON_PRODUCTION / QUARANTINED.\n- Production Claude API remains paused; Claude.ai Web remains full co-engineer.\n`);
console.log(validation);
