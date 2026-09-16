import assert from 'node:assert/strict';
import {BENCHMARK_SUITES,benchmarkSuiteFor,scoreBenchmarkRun} from './image-render/benchmark-suite.js';

// Section 6: every benchmarked task declares the dimensions it is judged on.
const expected={
  TEXT_TO_IMAGE:['promptAdherence','objectCount','composition','anatomy','styleAccuracy','textAccuracy'],
  REFERENCE_GENERATION:['identitySimilarity','wardrobeConsistency','keyShapeColor','subjectCount','poseComposition','backgroundAdherence'],
  IMAGE_EDIT_LOCAL:['targetEditSuccess','preserveUneditedRegions','identityPreservation','geometryPreservation'],
  IMAGE_EDIT_GLOBAL:['instructionAdherence','structurePreservation'],
  CHARACTER_CONSISTENCY:['identityAcrossScenes','wardrobe','proportions','facialHeadTraits','accessoryConsistency'],
  TARGETED_REPAIR:['localDefectFixed','surroundingPixelsPreserved','noFullSceneDrift'],
};
for(const [task,dimensions] of Object.entries(expected)){
  assert.deepEqual(benchmarkSuiteFor(task).dimensions.map(d=>d.id),dimensions,task);
}
assert.equal(benchmarkSuiteFor('UNKNOWN_TASK'),null);
assert.ok(Object.keys(BENCHMARK_SUITES).length>=6);

// Reference tasks weight fidelity above everything else; repair weights preservation.
const ref=benchmarkSuiteFor('REFERENCE_GENERATION');
const identity=ref.dimensions.find(d=>d.id==='identitySimilarity');
assert.ok(ref.dimensions.every(d=>d.id==='identitySimilarity'||d.weight<=identity.weight));
const repair=benchmarkSuiteFor('TARGETED_REPAIR');
assert.ok(repair.dimensions.find(d=>d.id==='surroundingPixelsPreserved').weight>=repair.dimensions.find(d=>d.id==='localDefectFixed').weight);

// A run is only scored on dimensions the critic actually measured, and a run missing a
// required dimension is not a pass — it is unverified.
let run=scoreBenchmarkRun('TEXT_TO_IMAGE',{promptAdherence:95,objectCount:100,composition:90,anatomy:88,styleAccuracy:92,textAccuracy:85});
assert.equal(run.ok,true);
assert.ok(run.score>85&&run.score<=100);
assert.deepEqual(run.missingDimensions,[]);

run=scoreBenchmarkRun('TEXT_TO_IMAGE',{promptAdherence:95});
assert.equal(run.ok,false);
assert.equal(run.reason,'incomplete_benchmark_dimensions');
assert.ok(run.missingDimensions.includes('anatomy'));

run=scoreBenchmarkRun('UNKNOWN_TASK',{});
assert.equal(run.ok,false);
assert.equal(run.reason,'unknown_benchmark_task');

// Scores are clamped, and a failing run reports honestly rather than rounding up.
run=scoreBenchmarkRun('TARGETED_REPAIR',{localDefectFixed:100,surroundingPixelsPreserved:10,noFullSceneDrift:20});
assert.equal(run.ok,true);
assert.ok(run.score<60,'destroying the surrounding image must not score well');

console.log('image render v4 benchmark suite contracts: PASS');
