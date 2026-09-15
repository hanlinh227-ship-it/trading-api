import assert from 'node:assert/strict';
import {applyCapabilityEvidence,capabilityEvidenceDiagnostics,enabledHardCapabilities} from './model-mesh/capability-evidence.js';
import {selectModelWorkers} from './model-mesh/selector.js';

function model(provider,modelId,family){return {
  provider_id:provider,model_id:modelId,model_family:family,
  free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',
  capabilities:{text_reasoning:{supported:true,score:0.9},coding:{supported:true,score:0.9}},
  quality_scores:{engineering:0.9,core:0.9},privacy_class:'public_safe',health:'healthy',
  quota_state:{state:'AVAILABLE'},context_window:131072,
};}

const models=[model('p1','m1','f1'),model('p2','m2','f2')];
const index={
  schema_version:1,source_sha:'a'.repeat(40),mode:'FREE_ONLY',routing_authority:false,reasoning_authority:false,
  coverage:{
    'engineering.coding':{domain:'engineering',capability:'coding',eligible_candidates:2,verified_candidates:2,coverage_ratio:1,requested_enabled:true,gate_eligible:true,enabled:true},
  },
  entries:[
    {candidate_key:'p1:m1',provider_id:'p1',model_id:'m1',model_family:'f1',capability_evidence:{coding:{state:'VERIFIED',score:0.91,evidence_ids:['e1'],measured_at:'2026-09-15T00:00:00Z'}}},
    {candidate_key:'p2:m2',provider_id:'p2',model_id:'m2',model_family:'WRONG-FAMILY',capability_evidence:{coding:{state:'VERIFIED',score:0.92,evidence_ids:['e2'],measured_at:'2026-09-15T00:00:00Z'}}},
  ],
};

const overlaid=applyCapabilityEvidence(models,index);
assert.equal(overlaid[0].capability_evidence.coding.state,'VERIFIED');
assert.deepEqual(overlaid[1].capability_evidence,{},'family mismatch must discard evidence');
assert.deepEqual(enabledHardCapabilities(index,'engineering'),['coding']);
assert.deepEqual(enabledHardCapabilities(index,'core'),[]);
assert.deepEqual(capabilityEvidenceDiagnostics(index),{indexLoaded:true,verifiedRecords:2,enabledHardGates:1});

const defaultSelected=selectModelWorkers({profile:'STANDARD',domain:'engineering',dataClass:'PUBLIC',models:overlaid,requiredCapability:'text_reasoning'});
assert.equal(defaultSelected.length,2,'without hardCapabilities, current selection behavior is preserved');

const hardSelected=selectModelWorkers({profile:'STANDARD',domain:'engineering',dataClass:'PUBLIC',models:overlaid,requiredCapability:'text_reasoning',hardCapabilities:['coding']});
assert.deepEqual(hardSelected.map(row=>row.provider_id),['p1'],'enabled coding gate must require VERIFIED measured evidence');

const noGateIndex={...index,coverage:{'engineering.coding':{...index.coverage['engineering.coding'],requested_enabled:false,enabled:false}}};
assert.deepEqual(enabledHardCapabilities(noGateIndex,'engineering'),[],'gate eligibility alone must not activate enforcement');

console.log('model mesh active candidate index runtime ok');
