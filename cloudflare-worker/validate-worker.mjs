import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const root=process.cwd(),errors=[];
function walk(dir){for(const ent of fs.readdirSync(dir,{withFileTypes:true})){if(ent.name==='node_modules'||ent.name==='.wrangler')continue;const p=path.join(dir,ent.name);if(ent.isDirectory())walk(p);else if(/\.(?:js|mjs)$/.test(ent.name)){try{execFileSync(process.execPath,['--check',p],{cwd:root,stdio:'pipe'});}catch(e){errors.push(`SYNTAX ${path.relative(root,p)}: ${String(e?.stderr||e?.message||e).trim()}`);}}}}
walk(root);
const required=['index.js','hub-v11.js','v11/native-runtime.js','v11/manual-market-hunter.js','v11/entry-plan.js','v11/market-policies.js','v11/store.js','engine-v77168.js','binance-control-plane.js','multi-ai-control-plane.js','binance-readonly-health.js','providers/telegram-client.js'];
for(const f of required)if(!fs.existsSync(path.join(root,f)))errors.push(`REQUIRED missing ${f}`);
const index=fs.readFileSync(path.join(root,'index.js'),'utf8'),hub=fs.readFileSync(path.join(root,'hub-v11.js'),'utf8'),hunter=fs.readFileSync(path.join(root,'v11/manual-market-hunter.js'),'utf8'),multi=fs.readFileSync(path.join(root,'multi-ai-control-plane.js'),'utf8');
if(!index.includes('hub-v11.js'))errors.push('SOURCE_OF_TRUTH index.js must import hub-v11.js');
if(!index.includes('const VERSION="V11"'))errors.push('SOURCE_OF_TRUTH index.js must expose VERSION V11');
if(!index.includes('signalOnlySourceOfTruth:"V11"'))errors.push('SOURCE_OF_TRUTH status must expose V11');
if(!index.includes('handleMultiAiControl'))errors.push('MULTI_AI control plane must be wired before normal routing');
if(!index.includes('handleBinanceReadonlyHealth'))errors.push('BINANCE readonly health must remain wired');
if(!hub.includes('scheduledNativeV11'))errors.push('V11 scheduler missing');
if(!hunter.includes('env.AI_BRIDGE.fetch'))errors.push('V11 AI hunter must use AI_BRIDGE VPC binding');
if(hunter.includes('V11_AI_BRIDGE_URL')||multi.includes('V11_AI_BRIDGE_URL'))errors.push('Legacy public AI bridge URL is forbidden');
for(const needle of ["/internal/multi-ai/health","/internal/multi-ai/review","token.actions.githubusercontent.com","refs/heads/main","workflow_dispatch","env.AI_BRIDGE.fetch"]){if(!multi.includes(needle))errors.push(`MULTI_AI invariant missing ${needle}`);}
if(multi.includes('api_key')||multi.includes('API_KEY'))errors.push('MULTI_AI control plane must not embed provider API keys');
if(errors.length){console.error(`Worker V11 preflight FAILED (${errors.length})`);for(const x of errors)console.error(`- ${x}`);process.exit(1);}
console.log('Worker V11 preflight PASS: V11 source-of-truth, native scheduler, private VPC AI bridge, OIDC Multi-AI gateway and separate Binance readonly health locked.');
