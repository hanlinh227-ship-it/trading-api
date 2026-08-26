import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const ID_RE=/^[a-f0-9]{32}$/i,UUID_RE=/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
const NAMESPACE_NAME='TRADING_V77_STATE',VPC_NAME='v11-ai-bridge';
function run(args){return execFileSync(process.platform==='win32'?'npx.cmd':'npx',['wrangler',...args],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:30000,env:process.env});}
function explicitKv(){for(const k of ['TRADING_KV_NAMESPACE_ID','CF_TRADING_KV_NAMESPACE_ID','CLOUDFLARE_KV_NAMESPACE_ID']){const v=String(process.env[k]||'').trim();if(ID_RE.test(v))return {id:v,source:k};}return null;}
function discoverKv(){try{const raw=run(['kv','namespace','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const x of rows){if(String(x?.title||x?.name||'')===NAMESPACE_NAME&&ID_RE.test(String(x?.id||'')))return {id:String(x.id),source:'WRANGLER_KV_DISCOVERY'};}for(const line of raw.split(/\r?\n/)){if(line.includes(NAMESPACE_NAME)){const m=line.match(/[a-f0-9]{32}/i);if(m)return {id:m[0],source:'WRANGLER_KV_DISCOVERY'};}}}catch{}return null;}
function explicitVpc(){const v=String(process.env.V11_AI_BRIDGE_SERVICE_ID||'').trim();return UUID_RE.test(v)?{id:v,source:'V11_AI_BRIDGE_SERVICE_ID'}:null;}
function discoverVpc(){try{const raw=run(['vpc','service','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const x of rows){if(String(x?.name||'')===VPC_NAME&&UUID_RE.test(String(x?.id||x?.service_id||'')))return {id:String(x.id||x.service_id),source:'WRANGLER_VPC_DISCOVERY'};}for(const line of raw.split(/\r?\n/)){if(line.includes(VPC_NAME)){const m=line.match(/[a-f0-9]{8}-[a-f0-9-]{27,36}/i);if(m&&UUID_RE.test(m[0]))return {id:m[0],source:'WRANGLER_VPC_DISCOVERY'};}}}catch{}return null;}
const kv=explicitKv()||discoverKv();if(!kv)throw new Error(`Unable to resolve existing ${NAMESPACE_NAME} KV namespace; deployment aborted.`);
const vpc=explicitVpc()||discoverVpc();if(!vpc)throw new Error(`Unable to resolve existing ${VPC_NAME} VPC Service. Set V11_AI_BRIDGE_SERVICE_ID or grant Connectivity Directory Read/Bind to the Cloudflare deploy token. Deployment aborted to prevent dropping AI_BRIDGE.`);
const revision=String(process.env.GITHUB_SHA||process.env.RUNTIME_REVISION||'LOCAL').trim();
const forexLive=/^(true|1|yes)$/i.test(String(process.env.FOREX_AUTO_LIVE||'false'))?'true':'false';
const bybitLive=/^(true|1|yes)$/i.test(String(process.env.BYBIT_AUTO_LIVE||'false'))?'true':'false';
const forexTargetUsd=String(process.env.FOREX_TARGET_USD||'500').trim();
const forexTargetDays=String(process.env.FOREX_TARGET_DAYS||'3').trim();
const forexTargetCycle=String(process.env.FOREX_TARGET_CYCLE_ID||'CYCLE_001').trim().slice(0,80)||'CYCLE_001';
const config={$schema:'./node_modules/wrangler/config-schema.json',name:'trading-v77-scanner',main:'index.js',compatibility_date:'2026-08-21',keep_vars:true,vars:{RUNTIME_REVISION:revision,BYBIT_AUTO_LIVE:bybitLive,FOREX_AUTO_LIVE:forexLive,FOREX_TARGET_USD:forexTargetUsd,FOREX_TARGET_DAYS:forexTargetDays,FOREX_TARGET_CYCLE_ID:forexTargetCycle},kv_namespaces:[{binding:'TRADING_STATE',id:kv.id}],vpc_services:[{binding:'AI_BRIDGE',service_id:vpc.id,remote:true}],triggers:{crons:['* * * * *']}};
fs.writeFileSync('wrangler.jsonc',`${JSON.stringify(config,null,2)}\n`,'utf8');
console.log(`Prepared wrangler.jsonc: TRADING_STATE=${kv.source}, AI_BRIDGE=${vpc.source}, RUNTIME_REVISION=${revision}, BYBIT_AUTO_LIVE=${bybitLive}, FOREX_AUTO_LIVE=${forexLive}, FOREX_TARGET=${forexTargetUsd}/${forexTargetDays}d, FOREX_TARGET_CYCLE_ID=${forexTargetCycle}.`);
