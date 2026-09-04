import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const ID_RE=/^[a-f0-9]{32}$/i,UUID_RE=/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
const NAMESPACE_NAME='TRADING_V77_STATE';
// Binding name AI_BRIDGE is retained only for backward-compatible Bybit private VPS transport.
// It has no strategy/AI decision authority in BTC Hyperscale.
const PROXY_NAMES=['unified-3ai-bridge','v11-ai-bridge'];
function run(args){return execFileSync(process.platform==='win32'?'npx.cmd':'npx',['wrangler',...args],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:30000,env:process.env});}
function yes(v){return /^(true|1|yes)$/i.test(String(v||'false'));}
function has(k){return Object.prototype.hasOwnProperty.call(process.env,k)&&String(process.env[k]??'').trim()!=='';}
function explicitKv(){for(const k of ['TRADING_KV_NAMESPACE_ID','CF_TRADING_KV_NAMESPACE_ID','CLOUDFLARE_KV_NAMESPACE_ID']){const v=String(process.env[k]||'').trim();if(ID_RE.test(v))return {id:v,source:k};}return null;}
function discoverKv(){try{const raw=run(['kv','namespace','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const x of rows){if(String(x?.title||x?.name||'')===NAMESPACE_NAME&&ID_RE.test(String(x?.id||'')))return {id:String(x.id),source:'WRANGLER_KV_DISCOVERY'};}for(const line of raw.split(/\r?\n/)){if(line.includes(NAMESPACE_NAME)){const m=line.match(/[a-f0-9]{32}/i);if(m)return {id:m[0],source:'WRANGLER_KV_DISCOVERY'};}}}catch{}return null;}
function explicitProxy(){for(const k of ['AI_BRIDGE_SERVICE_ID','V11_AI_BRIDGE_SERVICE_ID']){const v=String(process.env[k]||'').trim();if(UUID_RE.test(v))return {id:v,source:k};}return null;}
function discoverProxy(){try{const raw=run(['vpc','service','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const name of PROXY_NAMES){for(const x of rows){if(String(x?.name||'')===name&&UUID_RE.test(String(x?.id||x?.service_id||'')))return {id:String(x.id||x.service_id),source:'WRANGLER_VPC_DISCOVERY:'+name};}for(const line of raw.split(/\r?\n/)){if(line.includes(name)){const m=line.match(/[a-f0-9]{8}-[a-f0-9-]{27,36}/i);if(m&&UUID_RE.test(m[0]))return {id:m[0],source:'WRANGLER_VPC_DISCOVERY:'+name};}}}}catch{}return null;}
const kv=explicitKv()||discoverKv();if(!kv)throw new Error(`Unable to resolve existing ${NAMESPACE_NAME} KV namespace; deployment aborted.`);
const proxy=explicitProxy()||discoverProxy();if(!proxy)throw new Error(`Unable to resolve existing VPS service used by Bybit private transport (${PROXY_NAMES.join(' or ')}); deployment aborted.`);
const revision=String(process.env.GITHUB_SHA||process.env.RUNTIME_REVISION||'LOCAL').trim();
const vars={RUNTIME_REVISION:revision};
for(const k of ['BYBIT_AUTO_ENABLED','BYBIT_AUTO_LIVE','BYBIT_BTC_LIVE_ACK','BYBIT_AUTO_DEMO','BYBIT_ALLOW_DIRECT_PUBLIC_FALLBACK','BYBIT_ALLOW_DIRECT_PRIVATE_FALLBACK'])if(has(k))vars[k]=yes(process.env[k])?'true':'false';
const config={$schema:'./node_modules/wrangler/config-schema.json',name:'trading-v77-scanner',main:'index.js',compatibility_date:'2026-08-21',keep_vars:true,vars,kv_namespaces:[{binding:'TRADING_STATE',id:kv.id}],vpc_services:[{binding:'AI_BRIDGE',service_id:proxy.id,remote:true}],triggers:{crons:['* * * * *']}};
fs.writeFileSync('wrangler.jsonc',`${JSON.stringify(config,null,2)}\n`,'utf8');
const shown=k=>Object.prototype.hasOwnProperty.call(vars,k)?vars[k]:'PRESERVE_EXISTING';
console.log(`Prepared BTC-only wrangler.jsonc: TRADING_STATE=${kv.source}, BYBIT_VPS_PROXY=${proxy.source}, RUNTIME_REVISION=${revision}, ENABLED=${shown('BYBIT_AUTO_ENABLED')}, LIVE_REQUEST=${shown('BYBIT_AUTO_LIVE')}, BTC_LIVE_ACK=${shown('BYBIT_BTC_LIVE_ACK')}, DEMO=${shown('BYBIT_AUTO_DEMO')}`);
