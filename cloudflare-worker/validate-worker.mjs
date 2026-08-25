import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const root=process.cwd(),errors=[];
function walk(dir){for(const ent of fs.readdirSync(dir,{withFileTypes:true})){if(ent.name==='node_modules'||ent.name==='.wrangler')continue;const p=path.join(dir,ent.name);if(ent.isDirectory())walk(p);else if(/\.(?:js|mjs)$/.test(ent.name)){try{execFileSync(process.execPath,['--check',p],{cwd:root,stdio:'pipe'});}catch(e){errors.push(`SYNTAX ${path.relative(root,p)}: ${String(e?.stderr||e?.message||e).trim()}`);}}}}
walk(root);
const required=['index.js','bybit-auto-hub.js','bybit-control-plane.js','bybit-readonly-health.js','bybit-auto-v1.js','bybit-auto-controller.js','bybit-scalp-engine.js','bybit-risk-guard.js','bybit-position-manager.js','bybit-ai-scalp-gate.js','bybit-learning-engine.js','multi-ai-control-plane.js','providers/telegram-client.js'];
for(const f of required)if(!fs.existsSync(path.join(root,f)))errors.push(`REQUIRED missing ${f}`);
const index=fs.readFileSync(path.join(root,'index.js'),'utf8'),hub=fs.readFileSync(path.join(root,'bybit-auto-hub.js'),'utf8'),multi=fs.readFileSync(path.join(root,'multi-ai-control-plane.js'),'utf8'),auto=fs.readFileSync(path.join(root,'bybit-auto-v1.js'),'utf8'),controller=fs.readFileSync(path.join(root,'bybit-auto-controller.js'),'utf8');
if(!index.includes('bybit-auto-hub.js'))errors.push('SOURCE_OF_TRUTH index.js must import bybit-auto-hub.js');
if(!index.includes('BYBIT_AUTO_TRADE_ONLY'))errors.push('SOURCE_OF_TRUTH status must expose BYBIT_AUTO_TRADE_ONLY');
if(!index.includes('signalV11Enabled:false'))errors.push('Signal V11 must stay disabled');
if(index.includes('signalHub.scheduled'))errors.push('Signal scheduler must stay disabled');
if(!index.includes('handleMultiAiControl'))errors.push('MULTI_AI control plane must remain wired');
if(!index.includes('handleBybitReadonlyHealth'))errors.push('BYBIT readonly health must remain wired');
if(!index.includes('handleBybitControlApi'))errors.push('BYBIT control plane must remain wired');
if(!index.includes('runBybitAutoControlled'))errors.push('BYBIT global auto controller must own scheduler execution');
for(const needle of ['ENTRY_SPACING_MS=5*60*1000','LOSS_PAUSE_MS=30*60*1000','LOSS_STREAK_TRIGGER=3','runBybitAutoV1','notifyLiveEntry','telegramApiRequest'])if(!controller.includes(needle))errors.push(`BYBIT controller invariant missing ${needle}`);
for(const needle of ['bybitRiskPreflight','manageBybitScalpPosition','PROTECTION_MISSING_AFTER_SET','UNTRACKED_LIVE_POSITION'])if(!auto.includes(needle))errors.push(`BYBIT hard protection invariant missing ${needle}`);
for(const needle of ['BYBIT_AUTO_TRADE_HUB','auto:dashboard','auto:positions','auto:ai','auto:risk','telegramEntryAlerts','compactPrices'])if(!hub.includes(needle))errors.push(`AUTO HUB invariant missing ${needle}`);
if(hub.includes('auto:target'))errors.push('AUTO HUB daily target UI must stay removed for continuous trading');
if(!hub.includes('Continuous trading')||!hub.includes('Daily target OFF'))errors.push('AUTO HUB must expose continuous trading with daily target OFF');
if(!controller.includes('profitTargetPolicy:"NONE_CANONICAL_RISK_GATES_ONLY"'))errors.push('BYBIT controller must keep daily target disabled and canonical risk gates only');
if(!hub.includes('/telegram/webhook'))errors.push('AUTO HUB Telegram webhook missing');
if(!controller.includes('SL ${compactPrice(p.sl,tick)} • -${usd(p.riskUsd)}'))errors.push('Telegram LIVE entry alert must expose compact SL and USD risk');
if(!controller.includes('TP ${compactPrice(p.tp,tick)} • +${usd(p.rewardUsd)}'))errors.push('Telegram LIVE entry alert must expose compact TP and USD reward');
if(multi.includes('V11_AI_BRIDGE_URL'))errors.push('Legacy public AI bridge URL is forbidden');
for(const needle of ["/internal/multi-ai/health","/internal/multi-ai/review","token.actions.githubusercontent.com","refs/heads/main","workflow_dispatch","env.AI_BRIDGE.fetch"]){if(!multi.includes(needle))errors.push(`MULTI_AI invariant missing ${needle}`);}
if(multi.includes('api_key')||multi.includes('API_KEY'))errors.push('MULTI_AI control plane must not embed provider API keys');
if(errors.length){console.error(`Worker AUTO preflight FAILED (${errors.length})`);for(const x of errors)console.error(`- ${x}`);process.exit(1);}
console.log('Worker AUTO preflight PASS: Bybit Auto Hub only + Telegram entry alerts + 3AI + continuous trading + daily target OFF + global spacing/loss pause + hard protection locked.');