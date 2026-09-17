import assert from 'node:assert/strict';
import {createBrainProjectStateClass,normalizeProjectId} from './brain-project-state.js';

class MemoryStorage{
  constructor(){this.map=new Map();}
  async get(key){return this.map.get(key);}
  async put(key,value){this.map.set(key,structuredClone(value));}
}

const fixedNow=Date.parse('2026-09-17T04:00:00.000Z');
const ProjectState=createBrainProjectStateClass({now:()=>fixedNow});
const storage=new MemoryStorage();
const object=new ProjectState({storage},{});

assert.equal(normalizeProjectId(' Image-Agent '),'image-agent');
for(const invalid of ['', '../trade', 'a/b', 'bad\nname', '.hidden', 'x'.repeat(81)]){
  assert.throws(()=>normalizeProjectId(invalid),/invalid_project_id/);
}

let res=await object.fetch(new Request('https://internal/state'));
assert.equal(res.status,404);
let payload=await res.json();
assert.equal(payload.ok,false);
assert.equal(payload.error,'project_not_initialized');

const initial={
  project_id:'image-agent',
  expected_version:0,
  active_phase:'production-operation',
  status:'active',
  latest_handoff:{
    summary:'Image V3 is canonical',
    blockers:[],
    next_actions:['render scene 1'],
    refs:['spec:scene-1'],
  },
  job_refs:[{subsystem:'image-v3',job_id:'logical-1',state:'running'}],
  runtime_revision:'a'.repeat(40),
  updated_by:'chatgpt',
};
res=await object.fetch(new Request('https://internal/state',{
  method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(initial),
}));
assert.equal(res.status,200);
payload=await res.json();
assert.equal(payload.ok,true);
assert.equal(payload.state.schema_version,1);
assert.equal(payload.state.version,1);
assert.equal(payload.state.project_id,'image-agent');
assert.equal(payload.state.updated_by,'chatgpt');
assert.equal(payload.state.updated_at,'2026-09-17T04:00:00.000Z');
assert.deepEqual(payload.state.job_refs,[{subsystem:'image-v3',job_id:'logical-1',state:'running'}]);
assert.equal('expected_version' in payload.state,false);

const stale={...initial,active_phase:'wrong',latest_handoff:{summary:'stale',blockers:[],next_actions:[],refs:[]},job_refs:[],runtime_revision:'b'.repeat(40),updated_by:'claude'};
res=await object.fetch(new Request('https://internal/state',{
  method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(stale),
}));
assert.equal(res.status,409);
payload=await res.json();
assert.equal(payload.ok,false);
assert.equal(payload.error,'project_state_conflict');
assert.equal(payload.currentVersion,1);

res=await object.fetch(new Request('https://internal/state'));
assert.equal(res.status,200);
payload=await res.json();
assert.equal(payload.state.active_phase,'production-operation');
assert.equal(payload.state.latest_handoff.summary,'Image V3 is canonical');

const update={...initial,expected_version:1,active_phase:'acceptance',status:'active',latest_handoff:{summary:'ready for production canary',blockers:[],next_actions:['run canary'],refs:[]},job_refs:[],runtime_revision:'c'.repeat(40),updated_by:'claude'};
res=await object.fetch(new Request('https://internal/state',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(update)}));
assert.equal(res.status,200);
payload=await res.json();
assert.equal(payload.state.version,2);
assert.equal(payload.state.active_phase,'acceptance');
assert.equal(payload.state.updated_by,'claude');

async function expectBad(body){
  const response=await object.fetch(new Request('https://internal/state',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(body)}));
  assert.equal(response.status,400);
  const value=await response.json();
  assert.equal(value.ok,false);
  assert.equal(value.error,'invalid_project_state');
}

await expectBad({...update,expected_version:2,unknown_field:true});
await expectBad({...update,expected_version:2,project_id:'../other'});
await expectBad({...update,expected_version:2,latest_handoff:{...update.latest_handoff,summary:'Authorization: Bearer super-secret-value'}});
await expectBad({...update,expected_version:2,latest_handoff:{...update.latest_handoff,summary:'-----BEGIN PRIVATE KEY-----\nsecret'}});
await expectBad({...update,expected_version:2,latest_handoff:{...update.latest_handoff,next_actions:Array.from({length:33},(_,i)=>`action-${i}`)}});
await expectBad({...update,expected_version:2,latest_handoff:{...update.latest_handoff,summary:'x'.repeat(4001)}});
await expectBad({...update,expected_version:2,job_refs:[{subsystem:'image-v3',job_id:'x'.repeat(161),state:'running'}]});

res=await object.fetch(new Request('https://internal/state',{method:'POST'}));
assert.equal(res.status,405);

console.log('BRAIN_PROJECT_STATE_TESTS=PASS');
