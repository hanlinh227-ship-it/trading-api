import assert from 'node:assert/strict';
import {rankImageModels} from './image-render/model-router.js';

const ranked=rankImageModels({
  models:[
    {name:'Fast Model',workerCount:8,performance:20,eta:1,queued:0},
    {name:'Preferred Model',workerCount:2,performance:15,eta:8,queued:1},
    {name:'Failing Model',workerCount:8,performance:30,eta:0,queued:0},
    {name:'Offline Model',workerCount:0,performance:100,eta:0,queued:0},
  ],
  preferredModels:['Preferred Model'],
  history:{
    'Failing Model':{failures:5,successes:0},
    'Preferred Model':{failures:0,successes:2},
  },
  limit:4,
});

assert.equal(ranked[0].name,'Preferred Model');
assert.ok(ranked[0].reasons.includes('preferred_model'));
assert.ok(ranked.find(x=>x.name==='Failing Model').score < ranked.find(x=>x.name==='Fast Model').score);
assert.ok(ranked.find(x=>x.name==='Offline Model').score < -500);
assert.equal(ranked.length,4);
assert.ok(ranked.every(x=>Number.isFinite(x.score)&&Array.isArray(x.reasons)));

const tied=rankImageModels({
  models:[
    {name:'Zulu',workerCount:1,performance:1,eta:1,queued:1},
    {name:'Alpha',workerCount:1,performance:1,eta:1,queued:1},
  ],
  limit:2,
});
assert.deepEqual(tied.map(x=>x.name),['Alpha','Zulu']);

const bounded=rankImageModels({models:Array.from({length:20},(_,i)=>({name:`M${i}`,workerCount:1,performance:1,eta:1,queued:0})),limit:99});
assert.equal(bounded.length,8);

console.log('IMAGE_RENDER_V2_MODEL_ROUTER_TEST=PASS');
