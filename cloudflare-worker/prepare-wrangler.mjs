import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const ID_RE=/^[a-f0-9]{32}$/i,UUID_RE=/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i,SHA_RE=/^[a-f0-9]{40}$/i;
const NAMESPACE_NAME='TRADING_V77_STATE';
const PROXY_NAMES=['unified-3ai-bridge','v11-ai-bridge'];
const SNAPSHOT_JSON=path.resolve('..','AI_SKILL_LIBRARY','v4','runtime','generated','skill_gateway_snapshot.json');
const SNAPSHOT_ESM=path.resolve('generated','skill-gateway-snapshot.js');
function run(args){return execFileSync(process.platform==='win32'?'npx.cmd':'npx',['wrangler',...args],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:30000,env:process.env});}
function gitHead(){try{return String(execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000})).trim();}catch{return '';}}
function explicitKv(){for(const k of ['TRADING_KV_NAMESPACE_ID','CF_TRADING_KV_NAMESPACE_ID','CLOUDFLARE_KV_NAMESPACE_ID']){const v=String(process.env[k]||'').trim();if(ID_RE.test(v))return {id:v,source:k};}return null;}
function discoverKv(){try{const raw=run(['kv','namespace','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const x of rows){if(String(x?.title||x?.name||'')===NAMESPACE_NAME&&ID_RE.test(String(x?.id||'')))return {id:String(x.id),source:'WRANGLER_KV_DISCOVERY'};}for(const line of raw.split(/\r?\n/)){if(line.includes(NAMESPACE_NAME)){const m=line.match(/[a-f0-9]{32}/i);if(m)return {id:m[0],source:'WRANGLER_KV_DISCOVERY'};}}}catch{}return null;}
function explicitProxy(){for(const k of ['AI_BRIDGE_SERVICE_ID','V11_AI_BRIDGE_SERVICE_ID']){const v=String(process.env[k]||'').trim();if(UUID_RE.test(v))return {id:v,source:k};}return null;}
function discoverProxy(){try{const raw=run(['vpc','service','list']);let rows=[];try{const j=JSON.parse(raw);rows=Array.isArray(j)?j:(j?.result||[]);}catch{}for(const name of PROXY_NAMES){for(const x of rows){if(String(x?.name||'')===name&&UUID_RE.test(String(x?.id||x?.service_id||'')))return {id:String(x.id||x.service_id),source:'WRANGLER_VPC_DISCOVERY:'+name};}for(const line of raw.split(/\r?\n/)){if(line.includes(name)){const m=line.match(/[a-f0-9]{8}-[a-f0-9-]{27,36}/i);if(m&&UUID_RE.test(m[0]))return {id:m[0],source:'WRANGLER_VPC_DISCOVERY:'+name};}}}}catch{}return null;}
function prepareSkillSnapshot(revision){
  if(!fs.existsSync(SNAPSHOT_JSON))return {prepared:false,reason:'snapshot_not_present'};
  const snapshot=JSON.parse(fs.readFileSync(SNAPSHOT_JSON,'utf8'));
  if(snapshot?.schema_version!==1||!SHA_RE.test(String(snapshot?.source_sha||'')))throw new Error('Invalid Skill Gateway snapshot metadata.');
  if(SHA_RE.test(revision)&&String(snapshot.source_sha).toLowerCase()!==revision.toLowerCase())throw new Error(`Skill Gateway snapshot SHA mismatch: snapshot=${snapshot.source_sha} runtime=${revision}`);
  fs.mkdirSync(path.dirname(SNAPSHOT_ESM),{recursive:true});
  fs.writeFileSync(SNAPSHOT_ESM,`export const SKILL_GATEWAY_SNAPSHOT=Object.freeze(${JSON.stringify(snapshot)});\n`,'utf8');
  return {prepared:true,sourceSha:snapshot.source_sha};
}
const kv=explicitKv()||discoverKv();if(!kv)throw new Error(`Unable to resolve existing ${NAMESPACE_NAME} KV namespace; deployment aborted.`);
const proxy=explicitProxy()||discoverProxy();if(!proxy)throw new Error(`Unable to resolve existing VPS service used by Bybit private transport (${PROXY_NAMES.join(' or ')}); deployment aborted.`);
const revision=String(process.env.GITHUB_SHA||process.env.CF_PAGES_COMMIT_SHA||process.env.RUNTIME_REVISION||gitHead()||'UNKNOWN').trim();
const skillSnapshot=prepareSkillSnapshot(revision);
// Runtime operator switches are deliberately NOT generated from build environment.
// keep_vars:true preserves the already-authorized dashboard values across code deploys,
// so a source update cannot silently flip LIVE/PAPER, ACK, DEMO or fallback authority.
const vars={RUNTIME_REVISION:revision};
const config={$schema:'./node_modules/wrangler/config-schema.json',name:'trading-v77-scanner',main:'index.js',compatibility_date:'2026-08-21',keep_vars:true,vars,kv_namespaces:[{binding:'TRADING_STATE',id:kv.id}],vpc_services:[{binding:'AI_BRIDGE',service_id:proxy.id,remote:true}]};
fs.writeFileSync('wrangler.jsonc',`${JSON.stringify(config,null,2)}\n`,'utf8');
console.log(`Prepared BTC-only wrangler.jsonc: TRADING_STATE=${kv.source}, BYBIT_VPS_PROXY=${proxy.source}, RUNTIME_REVISION=${revision}, SKILL_GATEWAY=${skillSnapshot.prepared?skillSnapshot.sourceSha:'NOT_COMPILED'}, RUNTIME_SWITCHES=PRESERVE_EXISTING, LIVE_ACK=PRESERVE_EXISTING, CRON=NONE_EVENT_DRIVER_ONLY`);
