import assert from 'node:assert/strict';
import {COGNITIVE_CORE_ID,COGNITIVE_CORE_TEXT,buildCognitiveMessages,_test} from './model-mesh/cognitive-core.js';

const worker={
  model_id:'local/test-model',
  model_family:'test-family',
  worker_role:'critic',
  capability_evidence:{
    reasoning:{state:'VERIFIED'},
    coding:{state:'DECLARED_ONLY'},
    verifier:{state:'VERIFIED'},
  },
};
const route={domain:'engineering'};
const messages=buildCognitiveMessages(worker,route,'Check this result.');
assert.equal(COGNITIVE_CORE_ID,'brain-cognition-v1');
assert.ok(COGNITIVE_CORE_TEXT.includes('Measured capability outranks declared capability.'));
assert.equal(messages.length,3);
assert.equal(messages[0].role,'system');
assert.equal(messages[1].role,'system');
assert.equal(messages[2].role,'user');
assert.ok(messages[1].content.includes('test-family'));
assert.ok(messages[1].content.includes('critic'));
assert.ok(messages[1].content.includes('reasoning'));
assert.ok(messages[1].content.includes('verifier'));
assert.equal(messages[1].content.includes('coding'),false);
assert.deepEqual(_test.verifiedCapabilities(worker),['reasoning','verifier']);
console.log('MODEL_COGNITIVE_CORE_TESTS=PASS');
