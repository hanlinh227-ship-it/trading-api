import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const SHA_RE=/^[0-9a-f]{40}$/;
function gitHead(){try{return String(execFileSync('git',['rev-parse','HEAD'],{cwd:here,encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000})).trim().toLowerCase();}catch{return '';}}
const sourcePath=path.resolve(here,process.env.MODEL_MESH_SNAPSHOT_PATH||'../AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json');
if(!fs.existsSync(sourcePath))throw new Error(`Model Mesh snapshot missing: ${sourcePath}`);
const snapshot=JSON.parse(fs.readFileSync(sourcePath,'utf8'));
if(snapshot?.schema_version!==1||snapshot?.mode!=='FREE_ONLY'||snapshot?.routing_authority!==false||snapshot?.reasoning_authority!==false||!SHA_RE.test(String(snapshot?.source_sha||'')))throw new Error('Model Mesh snapshot metadata invalid');
const expected=String(process.env.RUNTIME_REVISION||process.env.GITHUB_SHA||process.env.CF_PAGES_COMMIT_SHA||gitHead()).trim().toLowerCase();
if(SHA_RE.test(expected)&&snapshot.source_sha!==expected)throw new Error(`Model Mesh exact-SHA mismatch: snapshot=${snapshot.source_sha} expected=${expected}`);
const outDir=path.join(here,'generated');fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(path.join(outDir,'model-mesh-snapshot.js'),`// Generated from validated model mesh snapshot. Do not edit.\nexport const MODEL_MESH_SNAPSHOT=Object.freeze(${JSON.stringify(snapshot)});\n`,'utf8');
console.log(`MODEL_MESH_ESM=PASS source_sha=${snapshot.source_sha} models=${(snapshot.models||[]).length}`);
