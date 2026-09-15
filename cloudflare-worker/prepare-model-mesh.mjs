import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const SHA_RE=/^[0-9a-f]{40}$/;
function gitHead(){try{return String(execFileSync('git',['rev-parse','HEAD'],{cwd:here,encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000})).trim().toLowerCase();}catch{return '';}}
const sourcePath=path.resolve(here,process.env.MODEL_MESH_SNAPSHOT_PATH||'../AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-snapshot.json');
const activeIndexPath=path.resolve(here,process.env.MODEL_MESH_ACTIVE_INDEX_PATH||'../AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-active-candidate-index.json');
const bindingsPath=path.resolve(here,process.env.MODEL_MESH_BINDINGS_PATH||'../AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json');
const freePolicyPath=path.resolve(here,process.env.MODEL_MESH_FREE_POLICY_PATH||'../AI_SKILL_LIBRARY/v4/model_mesh/free_only_policy.json');
const runtimePolicyPath=path.resolve(here,process.env.MODEL_MESH_POLICY_PATH||'../AI_SKILL_LIBRARY/v4/runtime/generated/model-mesh-policy.json');
if(!fs.existsSync(sourcePath))throw new Error(`Model Mesh snapshot missing: ${sourcePath}`);
if(!fs.existsSync(activeIndexPath))throw new Error(`Model Mesh Active Candidate Index missing: ${activeIndexPath}`);
if(!fs.existsSync(bindingsPath))throw new Error(`Model Mesh runtime bindings missing: ${bindingsPath}`);
if(!fs.existsSync(freePolicyPath))throw new Error(`Model Mesh FREE_ONLY policy missing: ${freePolicyPath}`);
if(!fs.existsSync(runtimePolicyPath))throw new Error(`Model Mesh compiled policy contract missing (run compile_model_mesh_policy.py): ${runtimePolicyPath}`);
const snapshot=JSON.parse(fs.readFileSync(sourcePath,'utf8'));
const activeIndex=JSON.parse(fs.readFileSync(activeIndexPath,'utf8'));
const bindingRegistry=JSON.parse(fs.readFileSync(bindingsPath,'utf8'));
const freePolicy=JSON.parse(fs.readFileSync(freePolicyPath,'utf8'));
const runtimePolicy=JSON.parse(fs.readFileSync(runtimePolicyPath,'utf8'));
if(snapshot?.schema_version!==1||snapshot?.mode!=='FREE_ONLY'||snapshot?.routing_authority!==false||snapshot?.reasoning_authority!==false||!SHA_RE.test(String(snapshot?.source_sha||'')))throw new Error('Model Mesh snapshot metadata invalid');
if(activeIndex?.schema_version!==1||activeIndex?.mode!=='FREE_ONLY'||activeIndex?.routing_authority!==false||activeIndex?.reasoning_authority!==false||!SHA_RE.test(String(activeIndex?.source_sha||''))||!Array.isArray(activeIndex?.entries)||!activeIndex?.coverage||typeof activeIndex.coverage!=='object')throw new Error('Model Mesh Active Candidate Index metadata invalid');
if(activeIndex.source_sha!==snapshot.source_sha)throw new Error(`Model Mesh Active Candidate Index source-SHA mismatch: index=${activeIndex.source_sha} snapshot=${snapshot.source_sha}`);
if(activeIndex.entries.length!==(snapshot.models||[]).length)throw new Error(`Model Mesh Active Candidate Index cardinality mismatch: index=${activeIndex.entries.length} snapshot=${(snapshot.models||[]).length}`);
const admitted=new Map((snapshot.models||[]).map(model=>[`${model.provider_id}:${model.model_id}`,String(model.model_family||'')]));
for(const entry of activeIndex.entries){
  const key=String(entry?.candidate_key||'');
  if(!admitted.has(key))throw new Error(`Model Mesh Active Candidate Index contains non-admitted model: ${key}`);
  if(admitted.get(key)!==String(entry?.model_family||''))throw new Error(`Model Mesh Active Candidate Index family mismatch: ${key}`);
}
if(bindingRegistry?.version!==1||bindingRegistry?.mode!=='FREE_ONLY'||!bindingRegistry?.bindings||typeof bindingRegistry.bindings!=='object')throw new Error('Model Mesh binding registry invalid');
if(runtimePolicy?.schema_version!==1||runtimePolicy?.mode!=='FREE_ONLY'||runtimePolicy?.paid_fallback!=='disabled')throw new Error('Model Mesh compiled policy contract invalid');
if(runtimePolicy?.max_parallel?.FAST!==0)throw new Error('Model Mesh policy must forbid external workers on FAST');
if(!Array.isArray(runtimePolicy?.selection_filters)||!runtimePolicy.selection_filters.length)throw new Error('Model Mesh policy selection filters missing');
if(runtimePolicy?.capability_evidence?.routing_authority!==false||runtimePolicy?.capability_evidence?.hard_gate?.default_enabled!==false)throw new Error('Model Mesh capability evidence Phase A policy invalid');
if(freePolicy?.schema_version!==1||freePolicy?.mode!=='FREE_ONLY'||JSON.stringify(freePolicy.eligible_statuses)!=='["recurring","account_specific"]'||freePolicy.free_verified_at_required!==true)throw new Error('Model Mesh FREE_ONLY policy invalid');
for(const [providerId,row] of Object.entries(bindingRegistry.bindings)){
  if(!row||typeof row!=='object'||typeof row.endpoint_family!=='string'||typeof row.endpoint_url!=='string'||typeof row.secret_name!=='string')throw new Error(`Model Mesh binding invalid: ${providerId}`);
  if(!/^[A-Z0-9_]+$/.test(row.secret_name))throw new Error(`Model Mesh secret name invalid: ${providerId}`);
  if(/(?:sk-|AIza|hf_)[A-Za-z0-9_-]{8,}/.test(JSON.stringify(row)))throw new Error(`Model Mesh credential value forbidden: ${providerId}`);
}
for(const model of snapshot.models||[]){
  const binding=bindingRegistry.bindings[model.provider_id];
  if(!binding)throw new Error(`Model Mesh model has no runtime binding: ${model.provider_id}`);
  const declared=String(model.endpoint_family||'');
  if(declared&&declared!=='native'&&declared!==binding.endpoint_family)throw new Error(`Model Mesh endpoint_family conflict for ${model.provider_id}: snapshot=${declared} binding=${binding.endpoint_family}`);
}

const expected=String(process.env.RUNTIME_REVISION||process.env.GITHUB_SHA||process.env.CF_PAGES_COMMIT_SHA||gitHead()).trim().toLowerCase();
if(SHA_RE.test(expected)&&snapshot.source_sha!==expected)throw new Error(`Model Mesh exact-SHA mismatch: snapshot=${snapshot.source_sha} expected=${expected}`);
if(SHA_RE.test(expected)&&activeIndex.source_sha!==expected)throw new Error(`Model Mesh Active Candidate Index exact-SHA mismatch: index=${activeIndex.source_sha} expected=${expected}`);
const outDir=path.join(here,'generated');fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(path.join(outDir,'model-mesh-policy.js'),`// Generated from the canonical Model Mesh policy. Do not edit.\nexport const MODEL_MESH_POLICY=Object.freeze(${JSON.stringify(runtimePolicy)});\n`,'utf8');
fs.writeFileSync(path.join(outDir,'model-mesh-snapshot.js'),`// Generated from validated model mesh snapshot. Do not edit.\nexport const MODEL_MESH_SNAPSHOT=Object.freeze(${JSON.stringify(snapshot)});\n`,'utf8');
fs.writeFileSync(path.join(outDir,'model-mesh-active-candidate-index.js'),`// Generated from validated Capability Evidence + admitted Model Mesh snapshot. Do not edit.\nexport const MODEL_MESH_ACTIVE_CANDIDATE_INDEX=Object.freeze(${JSON.stringify(activeIndex)});\n`,'utf8');
fs.writeFileSync(path.join(outDir,'model-mesh-bindings.js'),`// Generated from public runtime binding metadata. Secret values are never embedded.\nexport const MODEL_MESH_BINDINGS=Object.freeze(${JSON.stringify(bindingRegistry.bindings)});\n`,'utf8');
fs.writeFileSync(path.join(outDir,'free-only-policy.js'),`// Generated from the canonical FREE_ONLY policy. Do not edit.\nexport const FREE_ONLY_POLICY=Object.freeze(${JSON.stringify(freePolicy)});\n`,'utf8');
console.log(`MODEL_MESH_ESM=PASS source_sha=${snapshot.source_sha} models=${(snapshot.models||[]).length} index_entries=${activeIndex.entries.length} bindings=${Object.keys(bindingRegistry.bindings).length} max_parallel=${JSON.stringify(runtimePolicy.max_parallel)} filters=${runtimePolicy.selection_filters.length}`);
