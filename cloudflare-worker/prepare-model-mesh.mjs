import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const SHA_RE=/^[0-9a-f]{40}$/;
function gitHead(){try{return String(execFileSync('git',['rev-parse','HEAD'],{cwd:here,encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000})).trim().toLowerCase();}catch{return '';}}
const sourcePath=path.resolve(here,process.env.MODEL_MESH_SNAPSHOT_PATH||'../AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json');
const bindingsPath=path.resolve(here,process.env.MODEL_MESH_BINDINGS_PATH||'../AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json');
const freePolicyPath=path.resolve(here,process.env.MODEL_MESH_FREE_POLICY_PATH||'../AI_SKILL_LIBRARY/v4/model_mesh/free_only_policy.json');
if(!fs.existsSync(sourcePath))throw new Error(`Model Mesh snapshot missing: ${sourcePath}`);
if(!fs.existsSync(bindingsPath))throw new Error(`Model Mesh runtime bindings missing: ${bindingsPath}`);
if(!fs.existsSync(freePolicyPath))throw new Error(`Model Mesh FREE_ONLY policy missing: ${freePolicyPath}`);
const snapshot=JSON.parse(fs.readFileSync(sourcePath,'utf8'));
const bindingRegistry=JSON.parse(fs.readFileSync(bindingsPath,'utf8'));
const freePolicy=JSON.parse(fs.readFileSync(freePolicyPath,'utf8'));
if(snapshot?.schema_version!==1||snapshot?.mode!=='FREE_ONLY'||snapshot?.routing_authority!==false||snapshot?.reasoning_authority!==false||!SHA_RE.test(String(snapshot?.source_sha||'')))throw new Error('Model Mesh snapshot metadata invalid');
if(bindingRegistry?.version!==1||bindingRegistry?.mode!=='FREE_ONLY'||!bindingRegistry?.bindings||typeof bindingRegistry.bindings!=='object')throw new Error('Model Mesh binding registry invalid');
if(freePolicy?.schema_version!==1||freePolicy?.mode!=='FREE_ONLY'||JSON.stringify(freePolicy.eligible_statuses)!=='["recurring","account_specific"]'||freePolicy.free_verified_at_required!==true)throw new Error('Model Mesh FREE_ONLY policy invalid');
for(const [providerId,row] of Object.entries(bindingRegistry.bindings)){
  if(!row||typeof row!=='object'||typeof row.endpoint_family!=='string'||typeof row.endpoint_url!=='string'||typeof row.secret_name!=='string')throw new Error(`Model Mesh binding invalid: ${providerId}`);
  if(!/^[A-Z0-9_]+$/.test(row.secret_name))throw new Error(`Model Mesh secret name invalid: ${providerId}`);
  if(/(?:sk-|AIza|hf_)[A-Za-z0-9_-]{8,}/.test(JSON.stringify(row)))throw new Error(`Model Mesh credential value forbidden: ${providerId}`);
}
const expected=String(process.env.RUNTIME_REVISION||process.env.GITHUB_SHA||process.env.CF_PAGES_COMMIT_SHA||gitHead()).trim().toLowerCase();
if(SHA_RE.test(expected)&&snapshot.source_sha!==expected)throw new Error(`Model Mesh exact-SHA mismatch: snapshot=${snapshot.source_sha} expected=${expected}`);
const outDir=path.join(here,'generated');fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(path.join(outDir,'model-mesh-snapshot.js'),`// Generated from validated model mesh snapshot. Do not edit.\nexport const MODEL_MESH_SNAPSHOT=Object.freeze(${JSON.stringify(snapshot)});\n`,'utf8');
fs.writeFileSync(path.join(outDir,'model-mesh-bindings.js'),`// Generated from public runtime binding metadata. Secret values are never embedded.\nexport const MODEL_MESH_BINDINGS=Object.freeze(${JSON.stringify(bindingRegistry.bindings)});\n`,'utf8');
fs.writeFileSync(path.join(outDir,'free-only-policy.js'),`// Generated from the canonical FREE_ONLY policy. Do not edit.\nexport const FREE_ONLY_POLICY=Object.freeze(${JSON.stringify(freePolicy)});\n`,'utf8');
console.log(`MODEL_MESH_ESM=PASS source_sha=${snapshot.source_sha} models=${(snapshot.models||[]).length} bindings=${Object.keys(bindingRegistry.bindings).length}`);
