import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolveModelHealthStore} from './model-mesh/health-state.js';
import {writeProbeHealth} from './model-mesh/health-store.js';
import {resolveLiveModels} from './model-mesh/runtime-health.js';

class StaleKV {
  constructor(){this.puts=[];}
  async get(){return null;}
  async put(key,value,options){this.puts.push({key,value,options});}
}

class StrongHealthStub {
  constructor(){this.rows=new Map();}
  async fetch(request){
    const url=new URL(request.url);
    const body=await request.json();
    if(url.pathname==='/get'){
      const row=this.rows.get(body.key)||null;
      if(row?.expiresAt&&row.expiresAt<=Date.now()){
        this.rows.delete(body.key);
        return Response.json({value:null});
      }
      return Response.json({value:row?.value??null});
    }
    if(url.pathname==='/put'){
      const ttl=Number(body.expirationTtl)||0;
      this.rows.set(body.key,{value:body.value,expiresAt:ttl?Date.now()+ttl*1000:null});
      return Response.json({ok:true});
    }
    return Response.json({error:'not_found'},{status:404});
  }
}

class StrongHealthNamespace {
  constructor(stub){this.stub=stub;this.names=[];}
  idFromName(name){this.names.push(name);return `id:${name}`;}
  get(){return this.stub;}
}

const sourceSha='a'.repeat(40);
const nowMs=Date.parse('2026-09-16T10:00:00Z');
const model={
  provider_id:'groq',
  model_id:'openai/gpt-oss-120b',
  model_family:'gpt-oss-120b',
  free_status:'account_specific',
  free_verified_at:'2026-09-16T00:00:00Z',
  usage_terms:'production_allowed',
  context_window:131072,
  health:'degraded',
  privacy_class:'public_safe',
  capabilities:{text_reasoning:{supported:true,score:0.8}},
  quality_scores:{},
};
const snapshot={schema_version:1,source_sha:sourceSha,mode:'FREE_ONLY',models:[model]};
const staleKv=new StaleKV();
const strongStub=new StrongHealthStub();
const strongNamespace=new StrongHealthNamespace(strongStub);
const env={TRADING_STATE:staleKv,MODEL_MESH_HEALTH:strongNamespace,GROQ_API_KEY:'configured'};

// Production regression: Workers KV can keep serving a cached negative/stale
// lookup after a successful probe write. Model Mesh health requires immediate
// read-after-write visibility, so the dedicated strong store must win whenever
// the binding exists.
const store=resolveModelHealthStore(env);
const written=await writeProbeHealth(store,model,{ok:true,latencyMs:17},{sourceSha,nowMs,delay:async()=>{}});
assert.equal(written.state,'LIVE_HEALTHY');
assert.equal(staleKv.puts.length,0,'health evidence must not be written through eventually-consistent KV when strong store is bound');
assert.deepEqual(strongNamespace.names,['model-mesh-health-v1']);

const live=await resolveLiveModels(snapshot,env,{nowMs});
assert.equal(live.length,1);
assert.equal(live[0].runtimeState,'LIVE_HEALTHY','fresh probe evidence must be immediately visible to runtime planning');
assert.equal(live[0].health,'healthy');

// Local tests and old deployments remain fail-closed/backward compatible when
// the new binding is absent; this fallback is not the production strong path.
assert.equal(resolveModelHealthStore({TRADING_STATE:staleKv}),staleKv);

// Deploy wiring is part of the regression contract. A unit-only fix that omits
// the binding/export/migration would pass locally and reproduce the production
// canary failure after deploy.
const wranglerPrep=fs.readFileSync('prepare-wrangler.mjs','utf8');
const wranglerExample=fs.readFileSync('wrangler.example.jsonc','utf8');
const workerEntry=fs.readFileSync('index.js','utf8');
for(const text of [wranglerPrep,wranglerExample]){
  assert.match(text,/MODEL_MESH_HEALTH/,'strong Model Mesh health binding must be deployed');
  assert.match(text,/ModelMeshHealthState/,'strong health Durable Object class must be configured');
  assert.match(text,/model-mesh-health-v1/,'strong health Durable Object migration must be declared');
}
assert.match(workerEntry,/export \{ModelMeshHealthState\}/,'Durable Object class must be exported from Worker entrypoint');

console.log('model mesh strong health store defeats stale KV read-after-write regression');
