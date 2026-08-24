import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const root=process.cwd(),errors=[];
function walk(dir){for(const ent of fs.readdirSync(dir,{withFileTypes:true})){if(ent.name==='node_modules'||ent.name==='.wrangler')continue;const p=path.join(dir,ent.name);if(ent.isDirectory())walk(p);else if(/\.(?:js|mjs)$/.test(ent.name)){try{execFileSync(process.execPath,['--check',p],{cwd:root,stdio:'pipe'});}catch(e){errors.push(`SYNTAX ${path.relative(root,p)}: ${String(e?.stderr||e?.message||e).trim()}`);}}}}
walk(root);
const required=['index.js','hub-v11.js','v11/native-runtime.js','v11/manual-market-hunter.js','v11/entry-plan.js','v11/market-policies.js','v11/store.js','engine-v77168.js','bybit-control-plane.js','bybit-readonly-health.js','bybit-auto-v1.js','bybit-auto-controller.js','bybit-scalp-engine.js','bybit-risk-guard.js','bybit-position-manager.js','bybit-ai-scalp-gate.js','bybit-learning-engine.js','multi-ai-control-plane.js','providers/telegram-client.js'];
for(const f of required)if(!fs.existsSync(path.join(root,f)))errors.push(`REQUIRED missing ${f}`);
const index=fs.readFileSync(path.join(root,'index.js'),'utf8'),hub=fs.readFileSync(path.join(root,'hub-v11.js'),'utf8'),hunter=fs.readFileSync(path.join(root,'v11/manual-market-hunter.js'),'utf8'),multi=fs.readFileSync(path.join(root,'multi-ai-control-plane.js'),'utf8'),auto=fs.readFileSync(path.join(root,'bybit-auto-v1.js'),'utf8'),controller=fs.readFileSync(path.join(root,'bybit-auto-controller.js'),'utf8');
if(!index.includes('hub-v11.js'))errors.push('SOURCE_OF_TRUTH index.js must import hub-v11.js');
if(!index.includes('const VERSION="V11"'))errors.push('SOURCE_OF_TRUTH index.js must expose VERSION V11');
if(!index.includes('signalOnlySourceOfTruth:"V11"'))errors.push('SOURCE_OF_TRUTH status must expose V11');
if(!index.includes('handleMultiAiControl'))errors.push('MULTI_AI control plane must remain wired');
if(!index.includes('handleBybitReadonlyHealth'))errors.push('BYBIT readonly health must remain wired');
if(!index.includes('handleBybitControlApi'))errors.push('BYBIT control plane must remain wired');
if(!index.includes('runBybitAutoControlled'))errors.push('BYBIT global auto controller must own scheduler execution');
for(const needle of ['ENTRY_SPACING_MS=5*60*1000','LOSS_PAUSE_MS=30*60*1000','LOSS_STREAK_TRIGGER=3','runBybitAutoV1'])if(!controller.includes(needle))errors.push(`BYBIT controller invariant missing ${needle}`);
for(const needle of ['bybitRiskPreflight','manageBybitScalpPosition','PROTECTION_MISSING_AFTER_SET','UNTRACKED_LIVE_POSITION'])if(!auto.includes(needle))errors.push(`BYBIT hard protection invariant missing ${needle}`);
if(!hub.includes('scheduledNativeV11'))errors.push('V11 scheduler missing');
if(!hunter.includes('env.AI_BRIDGE.fetch'))errors.push('V11 AI hunter must use AI_BRIDGE VPC binding');
if(hunter.includes('V11_AI_BRIDGE_URL')||multi.includes('V11_AI_BRIDGE_URL'))errors.push('Legacy public AI bridge URL is forbidden');
for(const needle of ["/internal/multi-ai/health","/internal/multi-ai/review","token.actions.githubusercontent.com","refs/heads/main","workflow_dispatch","env.AI_BRIDGE.fetch"]){if(!multi.includes(needle))errors.push(`MULTI_AI invariant missing ${needle}`);}
if(multi.includes('api_key')||multi.includes('API_KEY'))errors.push('MULTI_AI control plane must not embed provider API keys');
if(errors.length){console.error(`Worker V11 preflight FAILED (${errors.length})`);for(const x of errors)console.error(`- ${x}`);process.exit(1);}
console.log('Worker V11 preflight PASS: Signal V11 + private 5AI + Bybit global entry spacing/loss pause + hard protection locked.');
