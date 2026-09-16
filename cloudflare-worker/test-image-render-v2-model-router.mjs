import assert from 'node:assert/strict';
import {rankImageModels} from './image-render/model-router.js';

const ranked=rankImageModels({
  models:[
    {name:'Fast',workerCount:8,performance:20,eta:1,queued:0},
    {name:'Preferred',workerCount:2,performance:15,eta:8,queued:1},
    {name:'Failing',workerCount:8,performance:30,eta:0,queued:0},
    {name:'Offline',workerCount:0,performance:200,eta:0,queued:0},
  ],
  preferredModels:['Preferred'],
  history:{Failing:{failures:5,successes:0}},
  limit:4,
});
assert.equal(ranked[0].name,'Preferred');
assert.ok(ranked.find(x=>x.name==='Failing').score<ranked.find(x=>x.name==='Fast').score);
assert.ok(ranked.find(x=>x.name==='Offline').score<0);
assert.ok(ranked[0].reasons.includes('preferred_model'));
console.log('IMAGE_RENDER_V2_MODEL_ROUTER_TEST=PASS');
