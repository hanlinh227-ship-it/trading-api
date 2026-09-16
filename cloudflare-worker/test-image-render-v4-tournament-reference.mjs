import assert from 'node:assert/strict';
import {CANDIDATE_TOURNAMENT_REFERENCE_WEIGHTS,selectBestCandidate} from './image-render/candidate-tournament.js';

const candidates=[{id:'pretty'},{id:'faithful'}];

// For a reference task, reference fidelity and lock compliance outrank overall aesthetics:
// "pretty" looks better overall but drifts from the reference, so "faithful" must win.
const criticResults={
  pretty:{ok:true,overallScore:96,confidence:0.99,dimensions:{promptAdherence:97,composition:98,anatomy:96,referenceFidelity:58,identityConsistency:55,lockCompliance:60}},
  faithful:{ok:true,overallScore:88,confidence:0.92,dimensions:{promptAdherence:90,composition:84,anatomy:88,referenceFidelity:95,identityConsistency:96,lockCompliance:97}},
};
let result=selectBestCandidate({candidates,criticResults,referenceTask:true,thresholds:{pass:85,referenceFidelity:85}});
assert.equal(result.selected.id,'faithful');
assert.equal(result.passed,true);
assert.ok(CANDIDATE_TOURNAMENT_REFERENCE_WEIGHTS.referenceFidelity>CANDIDATE_TOURNAMENT_REFERENCE_WEIGHTS.composition);

// A reference task must never be reported verified when the critic produced no reference
// fidelity evidence at all: a high overall score is not reference fidelity.
result=selectBestCandidate({
  candidates:[{id:'no-evidence'}],
  criticResults:{'no-evidence':{ok:true,overallScore:97,confidence:0.99,dimensions:{promptAdherence:98,composition:96}}},
  referenceTask:true,
  thresholds:{pass:85,referenceFidelity:85},
});
assert.equal(result.passed,false);
assert.equal(result.verified,false);
assert.ok(result.selected.unverifiedReasons.includes('reference_fidelity_not_evaluated'));

// An explicit lock the critic reports as broken also blocks verification.
result=selectBestCandidate({
  candidates:[{id:'lock-broken'}],
  criticResults:{'lock-broken':{ok:true,overallScore:94,confidence:0.95,dimensions:{referenceFidelity:92,identityConsistency:91,lockCompliance:40}}},
  referenceTask:true,
  thresholds:{pass:85,referenceFidelity:85,lockCompliance:85},
});
assert.equal(result.passed,false);
assert.ok(result.selected.unverifiedReasons.includes('lock_compliance_below_threshold'));

// Non-reference tasks keep the existing generic behaviour.
result=selectBestCandidate({
  candidates:[{id:'t2i'}],
  criticResults:{t2i:{ok:true,overallScore:93,confidence:0.95,dimensions:{promptAdherence:94,composition:92}}},
  thresholds:{pass:85},
});
assert.equal(result.passed,true);
assert.equal(result.verified,true);

console.log('image render v4 reference tournament contracts: PASS');
