import fs from 'node:fs';
import {HEALTH_REFRESH_CRON,assertHealthOnlyCrons} from './model-mesh/scheduled-health.js';
import {execFileSync} from 'node:child_process';
const ID_RE=/^[a-f0-9]{32}$/i,UUID_RE=/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
const NAMESPACE_NAME='TRADING_V77_STATE';
const PROXY_NAMES=['unified-3ai-bridge','v11-ai-bridge'];
function run(args){return execFileSync(process.platform==='win32'?'npx.cmd':'npx',['wrangler',...args],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:30000,env:process.env});}
function gitHead(){try{return String(execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000})).trim();}catch{return '';}}
function explicitKv(){for(const k of ['TRADING_KV_NAMESPACE_ID','CF_TRADING_KV_NAMESPACE_ID','CLOUDFLARE_KV_NAMESPACE_ID']){const v=String(process.env[k]||'').trim();if(ID_RE.test(v))return {id:v,source:k};}return null;}
function explicitBrainKv(){const v=String(process.env.BRAIN_KV_NAMESPACE_ID||'').trim();return ID_RE.test(v)?{id:v,source:'BRAIN_KV_NAMESPACE_ID'}:null;}
function discoverKv(){try{const raw=run(['kv','namespace','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const x of rows){if(String(x?.title||x?.name||'')===NAMESPACE_NAME&&ID_RE.test(String(x?.id||'')))return {id:String(x.id),source:'WRANGLER_KV_DISCOVERY'};}for(const line of raw.split(/\r?\n/)){if(line.includes(NAMESPACE_NAME)){const m=line.match(/[a-f0-9]{32}/i);if(m)return {id:m[0],source:'WRANGLER_KV_DISCOVERY'};}}}catch{}return null;}
function explicitProxy(){for(const k of ['AI_BRIDGE_SERVICE_ID','V11_AI_BRIDGE_SERVICE_ID']){const v=String(process.env[k]||'').trim();if(UUID_RE.test(v))return {id:v,source:k};}return null;}
function discoverProxy(){try{const raw=run(['vpc','service','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const name of PROXY_NAMES){for(const x of rows){if(String(x?.name||'')===name&&UUID_RE.test(String(x?.id||x?.service_id||'')))return {id:String(x.id||x.service_id),source:'WRANGLER_VPC_DISCOVERY:'+name};}for(const line of raw.split(/\r?\n/)){if(line.includes(name)){const m=line.match(/[a-f0-9]{8}-[a-f0-9-]{27,36}/i);if(m&&UUID_RE.test(m[0]))return {id:m[0],source:'WRANGLER_VPC_DISCOVERY:'+name};}}}}catch{}return null;}
const kv=explicitKv()||discoverKv();if(!kv)throw new Error(`Unable to resolve existing ${NAMESPACE_NAME} KV namespace; deployment aborted.`);
const brainKv=explicitBrainKv();
const proxy=explicitProxy()||discoverProxy();if(!proxy)throw new Error(`Unable to resolve existing VPS service used by Bybit private transport (${PROXY_NAMES.join(' or ')}); deployment aborted.`);
const revision=String(process.env.GITHUB_SHA||process.env.CF_PAGES_COMMIT_SHA||process.env.RUNTIME_REVISION||gitHead()||'UNKNOWN').trim();
// Financial/live operator switches remain dashboard-controlled and are never generated here.
// Model Mesh and public-data image rendering are explicitly source-authorized; both remain protected by authenticated execution tokens.
const vars={RUNTIME_REVISION:revision,MODEL_MESH_EXECUTION_ENABLED:'1',IMAGE_RENDER_EXECUTION_ENABLED:'1'};
const kvNamespaces=[{binding:'TRADING_STATE',id:kv.id}];
if(brainKv)kvNamespaces.push({binding:'BRAIN_STATE',id:brainKv.id});
const config={$schema:'./node_modules/wrangler/config-schema.json',name:'trading-v77-scanner',main:'index.js',compatibility_date:'2026-08-21',keep_vars:true,vars,ai:{binding:'AI'},kv_namespaces:kvNamespaces,durable_objects:{bindings:[{name:'TINYFISH_CIRCUIT',class_name:'TinyFishCircuit'},{name:'MODEL_MESH_HEALTH',class_name:'ModelMeshHealthState'},{name:'IMAGE_RENDER_BATCH',class_name:'ImageRenderBatchState'},{name:'IMAGE_LOGICAL_JOB',class_name:'ImageLogicalJobState'},{name:'BRAIN_PROJECT_STATE',class_name:'BrainProjectState'}]},migrations:[{tag:'tinyfish-circuit-v1',new_sqlite_classes:['TinyFishCircuit']},{tag:'model-mesh-health-v1',new_sqlite_classes:['ModelMeshHealthState']},{tag:'image-render-batch-v1',new_sqlite_classes:['ImageRenderBatchState']},{tag:'image-logical-job-v1',new_sqlite_classes:['ImageLogicalJobState']},{tag:'brain-project-state-v1',new_sqlite_classes:['BrainProjectState']}],vpc_services:[{binding:'AI_BRIDGE',service_id:proxy.id,remote:true}],triggers:{crons:[HEALTH_REFRESH_CRON]}};
assertHealthOnlyCrons(config.triggers.crons);
fs.writeFileSync('wrangler.jsonc',`${JSON.stringify(config,null,2)}\n`,'utf8');
console.log(`Prepared BTC-only wrangler.jsonc: TRADING_STATE=${kv.source}, BRAIN_STATE=${brainKv?.source||'TRADING_STATE_NAMESPACED_FALLBACK'}, BRAIN_PROJECT_STATE=DURABLE_OBJECT_STRONG, MODEL_MESH_HEALTH=DURABLE_OBJECT_STRONG, IMAGE_RENDER_BATCH=DURABLE_OBJECT_STRONG, IMAGE_LOGICAL_JOB=DURABLE_OBJECT_STRONG, BYBIT_VPS_PROXY=${proxy.source}, RUNTIME_REVISION=${revision}, MODEL_MESH_EXECUTION=ENABLED_AUTHENTICATED, IMAGE_RENDER_EXECUTION=ENABLED_AUTHENTICATED_PUBLIC_ONLY, IMAGE_INFERENCE=WORKERS_AI_FREE_ALLOCATION_HARD_STOP, FINANCIAL_RUNTIME_SWITCHES=PRESERVE_EXISTING, LIVE_ACK=PRESERVE_EXISTING, CRON=${config.triggers.crons.join(',')}_MODEL_MESH_HEALTH_ONLY`);
