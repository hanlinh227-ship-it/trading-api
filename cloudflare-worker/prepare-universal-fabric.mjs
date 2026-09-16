import fs from 'node:fs';
import path from 'node:path';
import {execFileSync,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'..');
const SHA_RE=/^[0-9a-f]{40}$/;

function gitHead(){
  try{return String(execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000})).trim().toLowerCase();}
  catch{return '';}
}
function pythonExecutable(){
  for(const candidate of ['python3','python']){
    const probe=spawnSync(candidate,['--version'],{encoding:'utf8',stdio:'ignore'});
    if(!probe.error&&probe.status===0)return candidate;
  }
  return '';
}

const expected=String(process.env.RUNTIME_REVISION||process.env.GITHUB_SHA||process.env.WORKERS_CI_COMMIT_SHA||process.env.CF_PAGES_COMMIT_SHA||gitHead()).trim().toLowerCase();
if(!SHA_RE.test(expected))throw new Error('Universal Fabric exact source SHA missing or invalid');
const sourcePath=path.resolve(root,process.env.UNIVERSAL_ADAPTERS_PATH||'AI_SKILL_LIBRARY/v4/runtime/generated/universal-adapters.json');
let payload=null;
if(fs.existsSync(sourcePath)){
  try{payload=JSON.parse(fs.readFileSync(sourcePath,'utf8'));}catch{payload=null;}
}
if(payload?.source_sha!==expected){
  const python=pythonExecutable();
  if(!python)throw new Error('Python is required to compile Universal adapter metadata');
  const compiler=path.join(root,'AI_SKILL_LIBRARY','v4','tools','compile_universal_adapters.py');
  const result=spawnSync(python,[compiler,'--root',root,'--source-sha',expected,'--output',path.relative(root,sourcePath)],{cwd:root,encoding:'utf8',stdio:'inherit'});
  if(result.error)throw result.error;
  if(result.status!==0)throw new Error(`compile_universal_adapters.py failed with exit code ${result.status}`);
  payload=JSON.parse(fs.readFileSync(sourcePath,'utf8'));
}
if(payload?.schema_version!==1||payload?.authority!==false||payload?.source_sha!==expected||!Array.isArray(payload?.adapters)||payload.adapters.length<1)throw new Error('Universal adapter metadata invalid');
for(const row of payload.adapters){
  if(!row?.id||!row?.token_binding||!Array.isArray(row?.scopes)||row.routing_authority!==false||row.reasoning_authority!==false)throw new Error(`Universal adapter row invalid: ${String(row?.id||'unknown')}`);
}
const outDir=path.join(here,'generated');
fs.mkdirSync(outDir,{recursive:true});
const out=path.join(outDir,'universal-adapters.js');
fs.writeFileSync(out,`// Generated from canonical Universal Brain adapter registry. Do not edit.\nexport const UNIVERSAL_ADAPTERS=Object.freeze(${JSON.stringify(payload)});\n`,'utf8');
console.log(`UNIVERSAL_ADAPTERS_ESM=PASS source_sha=${payload.source_sha} adapters=${payload.adapters.length}`);
