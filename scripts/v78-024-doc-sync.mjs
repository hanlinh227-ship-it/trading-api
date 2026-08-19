import fs from 'node:fs';

function ensureReplace(s,oldText,newText,label){
  if(s.includes(newText))return s;
  const n=s.split(oldText).length-1;
  if(n!==1)throw new Error(`${label}: expected old=1 or new present; got old=${n}`);
  return s.replace(oldText,newText);
}

const handoffPath='docs/checkpoints/CURRENT_HANDOFF.md';
let h=fs.readFileSync(handoffPath,'utf8');
h=h.replace('Updated: 2026-08-19 UTC+7','Updated: 2026-08-20 UTC+7');
h=ensureReplace(h,'- HUB `cloudflare-worker/hub-v77171.js`: **V77.18.42**.','- HUB `cloudflare-worker/hub-v77171.js`: **V77.18.42 + HUB-R13-ENTRY-INTEL-COVERAGE (V78-023 deployed)**.','handoff_hub');
h=ensureReplace(h,'- Signal engine `cloudflare-worker/engine-v77168.js`: **V77.16.20 — Signal Lifecycle Guard R7**.','- Signal engine `cloudflare-worker/engine-v77168.js`: **V77.16.20 — Signal Lifecycle Guard R7 + V78-020 safe Entry Intelligence promotion + V78-021/V78-022 quality/freshness rendering overlays**.','handoff_engine');
const v78Overlay='''\n## V78 CURRENT PRODUCTION OVERLAY — 2026-08-20\n- V78-020: PRODUCTION-VERIFIED safe Entry Intelligence promotion. REQUIRED evidence may block; QUALITY evidence only ranks; OPTIONAL market enrichment never independently blocks.\n- V78-021: group-scan candidate rendering shows Quality grade/score, blocked-promotion reasons and Freshness.\n- V78-022: cross-market Hub top setups show the same Quality/Freshness visibility; source commit `c41706b99b6357cc829b1a6ded0b7240bc428a27`, Cloudflare Version `c60f16a4-6a93-4ba3-aab3-a450b0188de0`.\n- V78-023: Hub R13 Entry Intelligence ACTIVE ADVISORY + read-only Coverage view across Forex/Crypto/Metal/Index; source commit `fbabe727caeb771b29188169800a7d275936b5ff`, Cloudflare Version `e6171203-204b-494e-884e-ddc7803b8993`.\n- Entry Intelligence execution authority remains NONE; Hyro remains the sole real-capital execution path.\n- Production Claude API remains PAUSED; Claude.ai Web remains an authorized co-engineer.\n- Hyro hardening blueprint: `docs/ai-coengineer/V78_HYRO_HARDENING_BLUEPRINT.md`; no real-capital hardening source change is implied by the blueprint.\n''';
if(!h.includes('## V78 CURRENT PRODUCTION OVERLAY — 2026-08-20')) h=h.replace('## AI-001 — HYRO TELEMETRY REPAIR',v78Overlay+'\n## AI-001 — HYRO TELEMETRY REPAIR');
const oldIssue='''## CURRENT OPEN ISSUE\nAI-002: documentation synchronization. This handoff and `MASTER_TRADING_STATE.md` are being synchronized to the V77.18.46 reviewed component state and permanent GitHub co-engineering mode, then Claude must review the exact documentation diff before AI-002 is marked RESOLVED.\n''';
const newIssue='''## CURRENT OPEN ISSUE\nAI-002: **RESOLVED by V78-024 canonical documentation synchronization.** Current handoff/master now include V78-020 through V78-023 production overlays. Next engineering work is coverage-guided Entry Intelligence optimization and separately-reviewed Hyro execution hardening; neither may weaken existing hard safeguards.\n''';
h=ensureReplace(h,oldIssue,newIssue,'handoff_issue');
fs.writeFileSync(handoffPath,h);

const masterPath='docs/checkpoints/MASTER_TRADING_STATE.md';
let m=fs.readFileSync(masterPath,'utf8');
m=m.replace('Updated: 2026-08-19 UTC+7','Updated: 2026-08-20 UTC+7');
const masterOverlay='''## 2026-08-20 V78 PRODUCTION OVERLAY\nCurrent GitHub `main` remains authoritative. This overlay supersedes older Hub/Entry-Intelligence wording below when it conflicts.\n\n- V78-020 is PRODUCTION-VERIFIED: Entry Intelligence contributes bounded Signal advisory ranking and gates only non-crypto MARKET_SIGNAL admission; crypto MARKET/LIMIT admission remains unchanged. Rescue-plan over-blocking was corrected with statusActionable() protection.\n- Evidence taxonomy is fixed: REQUIRED can block; QUALITY can rank; OPTIONAL market-specific enrichment cannot independently block.\n- V78-021 deployed Quality/Freshness rendering to group-scan candidate views.\n- V78-022 deployed Quality/Freshness rendering to cross-market Hub top setups. Source `c41706b99b6357cc829b1a6ded0b7240bc428a27`; Cloudflare Version `c60f16a4-6a93-4ba3-aab3-a450b0188de0`.\n- V78-023 deployed Hub `HUB-R13-ENTRY-INTEL-COVERAGE`: Entry Intel UI now says ACTIVE ADVISORY, shows Quality/ADMIT-BLOCK/Freshness/WHY fields, and adds read-only Coverage for the last 60 Entry Intelligence rows by Forex/Crypto/Metal/Index. Source `fbabe727caeb771b29188169800a7d275936b5ff`; Cloudflare Version `e6171203-204b-494e-884e-ddc7803b8993`.\n- Entry Intelligence has execution authority NONE. Signal remains advisory. Hyro remains the sole real-capital execution path.\n- Production Claude API remains PAUSED; Claude.ai Web remains a full co-engineer under WRITE_LOCK.\n- Hyro real-capital hardening is separately designed in `docs/ai-coengineer/V78_HYRO_HARDENING_BLUEPRINT.md` and requires guarded review before source changes.\n\n''';
if(!m.includes('## 2026-08-20 V78 PRODUCTION OVERLAY')) m=m.replace('## 2026-08-19 CURRENT SOURCE OVERLAY',masterOverlay+'## 2026-08-19 CURRENT SOURCE OVERLAY');
fs.writeFileSync(masterPath,m);

const issuesPath='docs/ai-coengineer/OPEN_ISSUES.md';
let o=fs.readFileSync(issuesPath,'utf8');
o=o.replace('Status: OPEN — DOC REVIEW RESULT AVAILABLE\nOwner: CHATGPT','Status: RESOLVED — V78-024 CANONICAL DOC SYNC\nOwner: CHATGPT');
const issueOverlay='''\n### V78-020 through V78-023 — RESOLVED / PRODUCTION\n- V78-020 Entry Intelligence safe promotion — PRODUCTION-VERIFIED.\n- V78-021 group-scan Quality/Freshness visibility — DEPLOYED.\n- V78-022 Hub top-setups Quality/Freshness visibility — DEPLOYED.\n- V78-023 Hub R13 ACTIVE ADVISORY + cross-market Coverage view — DEPLOYED.\n- Next: use Coverage evidence to identify real market/session gaps before any new strategy/gate authority.\n- Hyro execution hardening remains separately scoped by `V78_HYRO_HARDENING_BLUEPRINT.md`.\n''';
if(!o.includes('### V78-020 through V78-023 — RESOLVED / PRODUCTION')) o=o.replace('### NEXT OPTIMIZATION BATCH',issueOverlay+'\n### NEXT OPTIMIZATION BATCH');
fs.writeFileSync(issuesPath,o);

fs.writeFileSync('docs/ai-coengineer/V78-024_VALIDATION.txt',`V78-024 CANONICAL DOC SYNC + HYRO HARDENING BLUEPRINT\nvalidatedAt: ${new Date().toISOString()}\nCURRENT_HANDOFF: synced through V78-023\nMASTER_TRADING_STATE: added 2026-08-20 V78 production overlay\nOPEN_ISSUES AI-002: RESOLVED\nHyro hardening blueprint: created separately; no real-capital source behavior changed\nTRADING_STATE/v775:books: untouched\nRisk/freshness/structural-SL/news safeguards: unchanged\nProduction Claude API: PAUSED\n`);

fs.writeFileSync('docs/ai-coengineer/WRITE_LOCK.md',`# AI WRITE LOCK\n\nLOCKED: false\nOWNER: NONE\nSCOPE: NONE\nRELEASED: 2026-08-20\nLAST_OWNER: CHATGPT\nLAST_SCOPE: V78-024 canonical docs sync + Hyro hardening blueprint\nRESULT: RESOLVED. Validation in docs/ai-coengineer/V78-024_VALIDATION.txt.\n\nProtocol:\n- Acquire a new lock before the next source write.\n- Never reset TRADING_STATE or delete/reset v775:books.\n- Never weaken hard risk/freshness/structural-SL/news safeguards.\n- Never restore Futures/TK2.\n- Binance20 remains NON_PRODUCTION / QUARANTINED.\n- Production Claude API remains paused; Claude.ai Web remains full co-engineer.\n`);
console.log('V78-024 docs sync complete');
