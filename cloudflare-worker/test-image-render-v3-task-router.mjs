import assert from 'node:assert/strict';
import {rankImageModels} from './image-render/task-router.js';

const candidates=[
  {providerId:'a',modelId:'character',supportedTasks:['CHARACTER_CONSISTENCY','TEXT_RENDER_EDIT','REFERENCE_GENERATION'],health:'healthy',queueEstimate:20,latencyMs:2000,maxResolution:{width:2048,height:2048},referenceSafe:true,taskScores:{CHARACTER_CONSISTENCY:96,TEXT_RENDER_EDIT:70,REFERENCE_GENERATION:90},criticPassRate:0.90,textRenderScore:70},
  {providerId:'b',modelId:'text',supportedTasks:['CHARACTER_CONSISTENCY','TEXT_RENDER_EDIT'],health:'healthy',queueEstimate:10,latencyMs:1500,maxResolution:{width:2048,height:2048},referenceSafe:true,taskScores:{CHARACTER_CONSISTENCY:75,TEXT_RENDER_EDIT:98},criticPassRate:0.92,textRenderScore:99},
  {providerId:'c',modelId:'down',supportedTasks:['CHARACTER_CONSISTENCY'],health:'unhealthy',queueEstimate:0,latencyMs:100,maxResolution:{width:4096,height:4096},referenceSafe:true,taskScores:{CHARACTER_CONSISTENCY:100},criticPassRate:1},
  {providerId:'unsafe',modelId:'unsafe-ref',supportedTasks:['REFERENCE_GENERATION'],health:'healthy',queueEstimate:0,latencyMs:100,maxResolution:{width:4096,height:4096},referenceSafe:false,taskScores:{REFERENCE_GENERATION:100},criticPassRate:1},
];

let ranked=rankImageModels({intent:{taskType:'CHARACTER_CONSISTENCY',target:{width:1024,height:1024},referenceAssets:[{id:'ref'}]},candidates,history:{}});
assert.equal(ranked[0].modelId,'character');
assert.ok(!ranked.some(item=>item.modelId==='down'));

ranked=rankImageModels({intent:{taskType:'TEXT_RENDER_EDIT',target:{width:1024,height:1024},referenceAssets:[]},candidates,history:{}});
assert.equal(ranked[0].modelId,'text');

ranked=rankImageModels({intent:{taskType:'CHARACTER_CONSISTENCY',target:{width:1024,height:1024},referenceAssets:[{id:'ref'}]},candidates,history:{'a::character':{byTask:{CHARACTER_CONSISTENCY:{qualityScore:60,criticPassRate:0.5}},retryCount:3}}});
assert.equal(ranked[0].modelId,'text');

assert.deepEqual(rankImageModels({intent:{taskType:'CHARACTER_CONSISTENCY',target:{width:4096,height:4096},referenceAssets:[{id:'ref'}]},candidates,history:{}}),[]);

// Reference-sensitive intent types must require referenceSafe even when the asset list
// is temporarily empty (for example before upload attachment resolution completes).
ranked=rankImageModels({intent:{taskType:'REFERENCE_GENERATION',target:{width:1024,height:1024},referenceAssets:[]},candidates,history:{}});
assert.deepEqual(ranked.map(item=>item.modelId),['character']);
assert.ok(!ranked.some(item=>item.modelId==='unsafe-ref'));

console.log('image render v3 task router contracts: PASS');
