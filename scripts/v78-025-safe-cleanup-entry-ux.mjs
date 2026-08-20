import fs from 'node:fs';
import {execFileSync} from 'node:child_process';

const providerPath='cloudflare-worker/providers/entry-intelligence.js';
const hubPath='cloudflare-worker/hub-v77171.js';
const expectedProvider='27860df6730d81092e47a536e7d2db9092c2c099';
const expectedHub='e4160944f299bbb5eade9b2a0d83a1e6f4ecdb4f';
const hash=p=>execFileSync('git',['hash-object',p],{encoding:'utf8'}).trim();
if(hash(providerPath)!==expectedProvider)throw new Error(`provider stale-write guard mismatch: ${hash(providerPath)}`);
if(hash(hubPath)!==expectedHub)throw new Error(`hub stale-write guard mismatch: ${hash(hubPath)}`);

let provider=fs.readFileSync(providerPath,'utf8');
const oldIndex='if(market==="index")return {session:first(existingSession(a),c?.indexSession),instrumentIdentity:first(c?.instrumentIdentity,a?.instrumentType,"CASH_INDEX"),crossIndexConfirmation:first(c?.crossIndexConfirmation,c?.relativeStrength,a?.relativeStrength),riskContext:first(c?.riskSentiment,canon?.riskSentiment)};';
const newIndex='if(market==="index")return {session:first(existingSession(a),c?.indexSession),instrumentIdentity:first(c?.instrumentIdentity,a?.instrumentType),crossIndexConfirmation:first(c?.crossIndexConfirmation,c?.relativeStrength,a?.relativeStrength),riskContext:first(c?.riskSentiment,canon?.riskSentiment)};';
if(!provider.includes(oldIndex))throw new Error('index identity fallback OLD block mismatch');
provider=provider.replace(oldIndex,newIndex);
fs.writeFileSync(providerPath,provider);

let hub=fs.readFileSync(hubPath,'utf8');
hub=hub.replace('UI_REV="HUB-R13-ENTRY-INTEL-COVERAGE"','UI_REV="HUB-R14-ENTRY-INTEL-CLARITY"');
const intelStart=hub.indexOf('async function entryIntelText(env)');
const coverageStart=hub.indexOf('async function entryCoverageText(env)');
const engineStart=hub.indexOf('async function engineJson(',coverageStart);
if(intelStart<0||coverageStart<0||engineStart<0)throw new Error('Hub function boundaries not found');
const newIntel=`async function entryIntelText(env){const rows=await getEntryIntelligenceShadow(env,12),x=rows[0]||null;if(!x)return "🧭 ENTRY INTELLIGENCE • V78-025\\n━━━━━━━━━━━━\\n⚪ Chưa có reasoning. Quét một thị trường để tạo dữ liệu.";const c=x.integrity?.core||{},m=x.integrity?.marketSpecific||{},blocks=x.integrity?.hardBlocks||[],r=x.reasoning||{},q=x.quality||{},pr=x.promotion||{};return ["🧭 ENTRY INTELLIGENCE • SIGNAL ADVISORY","━━━━━━━━━━━━",\`${x.symbol||"—"} • ${String(x.market||"unknown").toUpperCase()} • ${x.existingDecision?.status||"UNKNOWN"}\`,\`⭐ Quality: ${q.grade||"?"} • ${q.score??"—"}/100 • ${pr.allowed===false?"⛔ SIGNAL BLOCK":"✅ SIGNAL OK"}\`,\`📡 Giá: ${x.quote?.freshness||"UNKNOWN"} • ${x.quote?.source||"—"}\`,\`🧩 Core: ${c.known||0}/${c.total||0} • Context: ${m.known||0}/${m.total||0}\`,\`⏱ WHY NOW: ${r.whyNow||"UNKNOWN"}\`,\`📍 WHY PRICE: ${r.whyPrice||"UNKNOWN"}\`,\`🛑 WHY SL: ${r.whySl||"UNKNOWN"}\`,\`🏁 WHY TP/RR: ${r.whyTp||"UNKNOWN"}\`,\`❌ Invalidates: ${r.invalidates||"UNKNOWN"}\`,blocks.length?\`🚧 REQUIRED block: ${blocks.join(", ")}\`:"✅ Không có REQUIRED block","🎯 Authority: SIGNAL ONLY • không tự đặt lệnh","Ranking/admission Signal advisory • Claude API không được gọi."].join("\\n");}\n`;
const newCoverage=`async function entryCoverageText(env){const rows=await getEntryIntelligenceShadow(env,240);if(!rows.length)return "📊 ENTRY INTELLIGENCE COVERAGE\\n━━━━━━━━━━━━\\n⚪ Chưa có dữ liệu. Quét từng thị trường để tạo evidence.";const markets=["forex","crypto","metal","index"],L=["📊 ENTRY INTELLIGENCE • COVERAGE","━━━━━━━━━━━━",\`Kho evidence gần nhất: ${rows.length} • tối đa 60 mẫu/thị trường\`];for(const market of markets){const xs=rows.filter(x=>String(x?.market||"").toLowerCase()===market).slice(0,60);if(!xs.length){L.push(\`⚪ ${market.toUpperCase()}: 0 mẫu\`);continue;}const live=xs.filter(x=>x?.quote?.freshness==="LIVE").length,blocked=xs.filter(x=>x?.promotion?.allowed===false).length,qs=xs.map(x=>Number(x?.quality?.score)).filter(Number.isFinite),avg=qs.length?Math.round(qs.reduce((a,b)=>a+b,0)/qs.length):null,missingCore={},missingCtx={};for(const x of xs){for(const k of x?.integrity?.missingCore||[])missingCore[k]=(missingCore[k]||0)+1;for(const [k,v] of Object.entries(x?.marketSpecific||{}))if(v==null||v==="UNKNOWN"||v==="MISSING")missingCtx[k]=(missingCtx[k]||0)+1;}const topCore=Object.entries(missingCore).sort((a,b)=>b[1]-a[1]).slice(0,2).map(([k,v])=>\`${k}:${v}\`).join(", ")||"none",topCtx=Object.entries(missingCtx).sort((a,b)=>b[1]-a[1]).slice(0,2).map(([k,v])=>\`${k}:${v}\`).join(", ")||"none";L.push(\`• ${market.toUpperCase()}: n=${xs.length} • LIVE ${live}/${xs.length} • Q~${avg??"—"} • SIGNAL BLOCK ${blocked}\`);L.push(\`  ↳ Core thiếu: ${topCore} • Context thiếu: ${topCtx}\`);}L.push("","REQUIRED có thể block • QUALITY chỉ rank • OPTIONAL/context không tự block.","Coverage read-only • Signal-only • không đổi execution authority.");return L.join("\\n");}\n`;
hub=hub.slice(0,intelStart)+newIntel+newCoverage+hub.slice(engineStart);
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
console.log('V78-025 applied: index identity fidelity, Hub clarity/coverage, one-shot workflows manual-only');
