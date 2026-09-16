import assert from 'node:assert/strict';
import {buildRenderReport,buildExportManifest} from './image-render/export-contract.js';

const state={
  batch_id:'b1',status:'complete_with_failures',
  scenes:[
    {scene_id:'01',status:'complete_unverified',attempts:[{model:'A',seed:'1',generation:{imageUrl:'https://example.invalid/1.webp'},qa_level:'STRUCTURAL',qa_result:'PASS_UNVERIFIED',qa_reasons:['visual_critic_unavailable']}]},
    {scene_id:'02',status:'failed_quality',attempts:[{model:'B',seed:'2',generation:{imageUrl:'http://unsafe.invalid/2.webp'},qa_level:'VISUAL',qa_result:'RETRY_MODEL',qa_reasons:['deformation']}]},
  ],
};
const report=buildRenderReport(state);
assert.equal(report.monetaryImageProviderCost,0);
assert.equal(report.freeOnly,true);
assert.equal(report.paidFallback,false);
assert.deepEqual(report.failedScenes,['02']);
assert.deepEqual(report.unverifiedScenes,['01']);
assert.equal(report.modelUsage.A,1);
assert.equal(report.modelUsage.B,1);
assert.deepEqual(report.seeds,['1','2']);
assert.equal(report.scenes[0].qa.level,'STRUCTURAL');
assert.ok(report.scenes[1].failureReasons.includes('deformation'));
const exported=buildExportManifest(state);
assert.deepEqual(exported.assets,[{sceneId:'01',fileName:'Scene_01.webp',url:'https://example.invalid/1.webp'}]);
assert.equal(exported.freeOnly,true);
assert.equal(exported.paidFallback,false);
assert.equal(exported.monetaryImageProviderCost,0);
console.log('IMAGE_RENDER_V2_EXPORT_TEST=PASS');
