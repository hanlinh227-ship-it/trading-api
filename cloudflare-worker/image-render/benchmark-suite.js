// Per-task benchmark definitions. A model is benchmarked on the dimensions that matter
// for the task it is being promoted for, never on one global "quality" number.
const suite=(taskType,purpose,dimensions)=>[taskType,{taskType,purpose,dimensions:Object.freeze(dimensions.map(Object.freeze))}];

export const BENCHMARK_SUITES=Object.freeze(Object.fromEntries([
  suite('TEXT_TO_IMAGE','does the render match what was asked for',[
    {id:'promptAdherence',weight:1.4},
    {id:'objectCount',weight:1.3},
    {id:'composition',weight:1.0},
    {id:'anatomy',weight:1.2},
    {id:'styleAccuracy',weight:0.9},
    {id:'textAccuracy',weight:1.0},
  ]),
  // Reference work is won on fidelity to the reference, not on looking good.
  suite('REFERENCE_GENERATION','is it the same subject as the reference',[
    {id:'identitySimilarity',weight:3.0},
    {id:'wardrobeConsistency',weight:1.8},
    {id:'keyShapeColor',weight:1.6},
    {id:'subjectCount',weight:1.5},
    {id:'poseComposition',weight:0.8},
    {id:'backgroundAdherence',weight:0.9},
  ]),
  // A local edit that damages the rest of the image is a failed edit.
  suite('IMAGE_EDIT_LOCAL','was only the target changed',[
    {id:'targetEditSuccess',weight:1.6},
    {id:'preserveUneditedRegions',weight:2.4},
    {id:'identityPreservation',weight:2.0},
    {id:'geometryPreservation',weight:1.6},
  ]),
  suite('IMAGE_EDIT_GLOBAL','was the instruction followed without losing the scene',[
    {id:'instructionAdherence',weight:1.5},
    {id:'structurePreservation',weight:1.5},
  ]),
  suite('CHARACTER_CONSISTENCY','is it the same character across scenes',[
    {id:'identityAcrossScenes',weight:3.0},
    {id:'wardrobe',weight:1.8},
    {id:'proportions',weight:1.6},
    {id:'facialHeadTraits',weight:2.2},
    {id:'accessoryConsistency',weight:1.2},
  ]),
  // Repair is judged mostly on what it left alone.
  suite('TARGETED_REPAIR','was the defect fixed without redrawing the scene',[
    {id:'localDefectFixed',weight:1.4},
    {id:'surroundingPixelsPreserved',weight:2.4},
    {id:'noFullSceneDrift',weight:2.0},
  ]),
]));

export function benchmarkSuiteFor(taskType){
  return BENCHMARK_SUITES[String(taskType||'')]||null;
}

const clamp=value=>Math.min(100,Math.max(0,Number(value)));

export function scoreBenchmarkRun(taskType,scores={}){
  const suiteDef=benchmarkSuiteFor(taskType);
  if(!suiteDef)return {ok:false,reason:'unknown_benchmark_task',score:0,missingDimensions:[]};
  const missingDimensions=suiteDef.dimensions
    .filter(dimension=>!Number.isFinite(Number(scores?.[dimension.id])))
    .map(dimension=>dimension.id);
  // An unmeasured dimension is not a zero and not a pass: the run is simply incomplete.
  if(missingDimensions.length)return {ok:false,reason:'incomplete_benchmark_dimensions',score:0,missingDimensions};
  let weighted=0;
  let total=0;
  for(const dimension of suiteDef.dimensions){
    weighted+=clamp(scores[dimension.id])*dimension.weight;
    total+=dimension.weight;
  }
  return {ok:true,reason:'benchmark_scored',score:Number((weighted/total).toFixed(4)),missingDimensions:[],taskType:suiteDef.taskType};
}
