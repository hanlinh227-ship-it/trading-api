import fs from 'node:fs';
import {execFileSync} from 'node:child_process';

const ID_RE=/^[a-f0-9]{32}$/i;
const NAMESPACE_NAME='TRADING_V77_STATE';

function explicitKvId(){
  for(const key of ['TRADING_KV_NAMESPACE_ID','CF_TRADING_KV_NAMESPACE_ID','CLOUDFLARE_KV_NAMESPACE_ID']){
    const v=String(process.env[key]||'').trim();
    if(ID_RE.test(v))return {id:v,source:key};
  }
  return null;
}

function parseNamespaceList(raw){
  const text=String(raw||'').trim();
  try{
    const j=JSON.parse(text);
    const rows=Array.isArray(j)?j:Array.isArray(j?.result)?j.result:[];
    for(const x of rows){
      const title=String(x?.title||x?.name||'');
      const id=String(x?.id||x?.namespace_id||'');
      if(title===NAMESPACE_NAME&&ID_RE.test(id))return id;
    }
  }catch{}
  const lines=text.split(/\r?\n/);
  for(const line of lines){
    if(!line.includes(NAMESPACE_NAME))continue;
    const m=line.match(/[a-f0-9]{32}/i);
    if(m)return m[0];
  }
  return null;
}

function discoverKvId(){
  try{
    const out=execFileSync(process.platform==='win32'?'npx.cmd':'npx',['wrangler','kv','namespace','list'],{encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:20000,env:process.env});
    const id=parseNamespaceList(out);
    if(id)return {id,source:'WRANGLER_KV_DISCOVERY'};
  }catch{}
  return null;
}

const resolved=explicitKvId()||discoverKvId();
if(!resolved){
  throw new Error(`Unable to resolve existing ${NAMESPACE_NAME} KV namespace. Set encrypted Cloudflare Build variable TRADING_KV_NAMESPACE_ID to the existing 32-character namespace ID. No new namespace will be created.`);
}

const config={
  $schema:'./node_modules/wrangler/config-schema.json',
  name:'trading-v77-scanner',
  main:'index.js',
  compatibility_date:'2026-08-18',
  keep_vars:true,
  kv_namespaces:[{binding:'TRADING_STATE',id:resolved.id}],
  triggers:{crons:['* * * * *']},
};

fs.writeFileSync('wrangler.jsonc',`${JSON.stringify(config,null,2)}\n`,'utf8');
console.log(`Prepared wrangler.jsonc with existing TRADING_STATE (${resolved.source}).`);
