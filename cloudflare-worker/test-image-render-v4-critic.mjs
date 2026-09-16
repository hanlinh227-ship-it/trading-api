import assert from 'node:assert/strict';
import {decideQualityAction,normalizeCriticResult} from './image-render/critic.js';

let result=normalizeCriticResult({ok:true,overallScore:94,confidence:0.96,dimensions:{promptAdherence:97,referenceFidelity:95,anatomy:91},problems:[],regions:[]});
assert.equal(result.ok,true);
assert.equal(result.overallScore,94);
assert.equal(result.confidence,0.96);
assert.equal(decideQualityAction(result,{passThreshold:85}).decision,'PASS');

result=normalizeCriticResult(null);
assert.equal(result.ok,false);
assert.equal(decideQualityAction(result,{strictVisual:true}).decision,'PASS_UNVERIFIED');

result=normalizeCriticResult({ok:true,overallScore:72,confidence:0.9,dimensions:{anatomy:45,promptAdherence:96},problems:[{code:'hand_anatomy',scope:'local',severity:'major',target:'left hand'}]});
assert.equal(decideQualityAction(result,{passThreshold:85}).decision,'REPAIR_LOCAL');

result=normalizeCriticResult({ok:true,overallScore:50,confidence:0.9,dimensions:{referenceFidelity:30},problems:[{code:'identity_mismatch',scope:'global',severity:'critical'}]});
assert.equal(decideQualityAction(result,{passThreshold:85}).decision,'RETRY_MODEL');

result=normalizeCriticResult({ok:true,overallScore:65,confidence:0.8,dimensions:{promptAdherence:40},problems:[{code:'prompt_mismatch',scope:'global',severity:'major'}]});
assert.equal(decideQualityAction(result,{passThreshold:85}).decision,'RETRY_PROMPT');

result=normalizeCriticResult({ok:true,overallScore:0,confidence:1,dimensions:{},problems:[{code:'unsafe_or_invalid_output',scope:'global',severity:'terminal'}]});
assert.equal(decideQualityAction(result,{passThreshold:85}).decision,'FAIL_TERMINAL');

console.log('image render v4 critic contracts: PASS');
