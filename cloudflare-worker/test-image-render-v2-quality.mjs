import assert from 'node:assert/strict';
import {evaluateImageQuality} from './image-render/quality-policy.js';

const scene={scene_id:'01',compiled_prompt:'one Max',expected_subject_count:1};
const good={imageUrl:'https://example.invalid/a.webp',censored:false,model:'m',state:'ok'};

const strictNoCritic=await evaluateImageQuality({scene,generation:good,qualityMode:'STRICT'});
assert.equal(strictNoCritic.decision,'PASS_UNVERIFIED');
assert.equal(strictNoCritic.sceneStatus,'complete_unverified');
assert.equal(strictNoCritic.verified,false);

const structural=await evaluateImageQuality({scene,generation:good,qualityMode:'STRUCTURAL'});
assert.equal(structural.decision,'PASS');
assert.equal(structural.sceneStatus,'complete');
assert.equal(structural.verified,true);

const censored=await evaluateImageQuality({scene,generation:{...good,censored:true},qualityMode:'STRICT'});
assert.equal(censored.decision,'RETRY_MODEL');
assert.ok(censored.reasons.includes('provider_censored'));

const insecure=await evaluateImageQuality({scene,generation:{...good,imageUrl:'http://example.invalid/a.webp'},qualityMode:'STRICT'});
assert.equal(insecure.decision,'FAIL_TERMINAL');
assert.ok(insecure.reasons.includes('invalid_image_url'));

const promptRepair=await evaluateImageQuality({
  scene,generation:good,qualityMode:'STRICT',
  visualCritic:async()=>({ok:true,pass:false,confidence:.97,reasons:['duplicate_subject']}),
});
assert.equal(promptRepair.decision,'RETRY_PROMPT');

const modelRetry=await evaluateImageQuality({
  scene,generation:good,qualityMode:'STRICT',
  visualCritic:async()=>({ok:true,pass:false,confidence:.95,reasons:['severe_anatomy']}),
});
assert.equal(modelRetry.decision,'RETRY_MODEL');

const visualPass=await evaluateImageQuality({
  scene,generation:good,qualityMode:'STRICT',
  visualCritic:async()=>({ok:true,pass:true,confidence:.94,reasons:[]}),
});
assert.equal(visualPass.decision,'PASS');
assert.equal(visualPass.verified,true);
assert.equal(visualPass.sceneStatus,'complete');

const criticUnavailable=await evaluateImageQuality({
  scene,generation:good,qualityMode:'STRICT',
  visualCritic:async()=>({ok:false,error:'no_free_visual_worker'}),
});
assert.equal(criticUnavailable.decision,'PASS_UNVERIFIED');
assert.equal(criticUnavailable.verified,false);

console.log('IMAGE_RENDER_V2_QUALITY_TEST=PASS');
