import assert from 'node:assert/strict';
import {evaluateImageQuality} from './image-render/quality-policy.js';

const scene={scene_id:'01',compiled_prompt:'one Max',expected_subject_count:1};
const good={imageUrl:'https://example.invalid/a.webp',censored:false,model:'m',state:'ok'};
assert.equal((await evaluateImageQuality({scene,generation:good,qualityMode:'STRICT'})).decision,'PASS_UNVERIFIED');
assert.equal((await evaluateImageQuality({scene,generation:{...good,censored:true},qualityMode:'STRICT'})).decision,'RETRY_MODEL');
assert.equal((await evaluateImageQuality({scene,generation:good,qualityMode:'STRICT',visualCritic:async()=>({ok:true,pass:false,confidence:.97,reasons:['duplicate_subject']})})).decision,'RETRY_PROMPT');
assert.equal((await evaluateImageQuality({scene,generation:good,qualityMode:'STRICT',visualCritic:async()=>({ok:true,pass:true,confidence:.94,reasons:[]})})).decision,'PASS');
console.log('IMAGE_RENDER_V2_QUALITY_TEST=PASS');
