import assert from 'node:assert/strict';
import {evaluateImageQuality} from './image-render/quality-policy.js';

const scene={scene_id:'01',compiled_prompt:'one Max',expected_subject_count:1};
const generation={imageUrl:'https://example.invalid/a.webp',censored:false,state:'ok',model:'M'};

const noCritic=await evaluateImageQuality({scene,generation,qualityMode:'STRICT'});
assert.equal(noCritic.decision,'PASS_UNVERIFIED');
assert.equal(noCritic.sceneStatus,'complete_unverified');
assert.equal(noCritic.qaLevel,'STRUCTURAL');

const structural=await evaluateImageQuality({scene,generation,qualityMode:'STRUCTURAL'});
assert.equal(structural.decision,'PASS');
assert.equal(structural.sceneStatus,'complete');

const censored=await evaluateImageQuality({scene,generation:{...generation,censored:true},qualityMode:'STRICT'});
assert.equal(censored.decision,'RETRY_MODEL');
assert.ok(censored.reasons.includes('censored_generation'));

const missing=await evaluateImageQuality({scene,generation:{...generation,imageUrl:null},qualityMode:'STRICT'});
assert.equal(missing.decision,'RETRY_SEED');

const visualPass=await evaluateImageQuality({
  scene,generation,qualityMode:'STRICT',
  visualCritic:async()=>({ok:true,decision:'PASS',confidence:0.93,reasons:['identity_ok']}),
});
assert.equal(visualPass.decision,'PASS');
assert.equal(visualPass.sceneStatus,'complete');
assert.equal(visualPass.qaLevel,'VISUAL');
assert.equal(visualPass.qaConfidence,0.93);

const visualRetry=await evaluateImageQuality({
  scene,generation,qualityMode:'STRICT',
  visualCritic:async()=>({ok:true,decision:'RETRY_PROMPT',confidence:0.88,reasons:['wardrobe_mismatch']}),
});
assert.equal(visualRetry.decision,'RETRY_PROMPT');
assert.ok(visualRetry.reasons.includes('wardrobe_mismatch'));
console.log('IMAGE_RENDER_V2_QUALITY_TEST=PASS');
