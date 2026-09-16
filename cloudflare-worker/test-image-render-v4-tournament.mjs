import assert from 'node:assert/strict';
import {selectBestCandidate} from './image-render/candidate-tournament.js';

const candidates=[
  {id:'a',imageUrl:'https://example.invalid/a.webp'},
  {id:'b',imageUrl:'https://example.invalid/b.webp'},
  {id:'c',imageUrl:'https://example.invalid/c.webp'},
];
const criticResults={
  a:{ok:true,overallScore:82,confidence:0.95,dimensions:{promptAdherence:90,referenceFidelity:88,anatomy:65,continuity:80}},
  b:{ok:true,overallScore:93,confidence:0.90,dimensions:{promptAdherence:94,referenceFidelity:96,anatomy:90,continuity:92}},
  c:{ok:true,overallScore:88,confidence:0.99,dimensions:{promptAdherence:91,referenceFidelity:80,anatomy:94,continuity:90}},
};
let result=selectBestCandidate({candidates,criticResults,thresholds:{pass:85,referenceFidelity:85}});
assert.equal(result.selected.id,'b');
assert.equal(result.passed,true);
assert.equal(result.ranked.length,3);

result=selectBestCandidate({candidates:[candidates[0]],criticResults:{a:{ok:false}},thresholds:{pass:85}});
assert.equal(result.selected.id,'a');
assert.equal(result.passed,false);
assert.equal(result.verified,false);

assert.throws(()=>selectBestCandidate({candidates:[]}),/candidate_required/);
console.log('image render v4 candidate tournament contracts: PASS');
