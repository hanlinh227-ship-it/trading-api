import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const SHA_RE=/^[0-9a-f]{40}$/;

function gitHead(){
  try{return String(execFileSync('git',['rev-parse','HEAD'],{cwd:here,encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000})).trim().toLowerCase();}
  catch{return '';}
}

const sourcePath=path.resolve(here,process.env.SKILL_GATEWAY_SNAPSHOT_PATH||'../AI_SKILL_LIBRARY/v4/runtime/generated/skill-gateway-snapshot.json');
if(!fs.existsSync(sourcePath))throw new Error(`Skill Gateway snapshot missing: ${sourcePath}`);
const snapshot=JSON.parse(fs.readFileSync(sourcePath,'utf8'));
if(snapshot?.schema_version!==1||!SHA_RE.test(String(snapshot?.source_sha||'')))throw new Error('Skill Gateway snapshot metadata invalid');
if(snapshot?.fallback_primary_skill!=='core_reasoning'||!snapshot?.capsules?.core_reasoning)throw new Error('Skill Gateway fallback/capsule contract invalid');
for(const profile of ['FAST','STANDARD','DEEP']){
  if(snapshot?.profiles?.[profile]?.primary_skill_count!==1||snapshot?.profiles?.[profile]?.skill_capsule_required!==true)throw new Error(`Skill Gateway profile invalid: ${profile}`);
}
const expected=String(process.env.RUNTIME_REVISION||process.env.GITHUB_SHA||process.env.CF_PAGES_COMMIT_SHA||gitHead()).trim().toLowerCase();
if(SHA_RE.test(expected)&&snapshot.source_sha!==expected)throw new Error(`Skill Gateway exact-SHA mismatch: snapshot=${snapshot.source_sha} expected=${expected}`);
const outDir=path.join(here,'generated');
fs.mkdirSync(outDir,{recursive:true});
const out=path.join(outDir,'skill-gateway-snapshot.js');
fs.writeFileSync(out,`// Generated from validated canonical GitHub Brain sources. Do not edit.\nexport const SKILL_GATEWAY_SNAPSHOT=Object.freeze(${JSON.stringify(snapshot)});\n`,'utf8');
console.log(`SKILL_GATEWAY_ESM=PASS source_sha=${snapshot.source_sha} skills=${Object.keys(snapshot.skills||{}).length} capsules=${Object.keys(snapshot.capsules||{}).length}`);
