import assert from 'node:assert/strict';
import {buildRenderReport,buildExportManifest} from './image-render/export-contract.js';

const state={batch_id:'b1',status:'complete_with_failures',scenes:[
  {scene_id:'01',status:'complete_unverified',attempts:[{model:'A',seed:'1',generation:{imageUrl:'https://example.invalid/1.webp'},qa:{qaLevel:'STRUCTURAL'}}]},
  {scene_id:'02',status:'failed_quality',attempts:[{model:'B',seed:'2',qa:{reasons:['deformation']}}]},
  {scene_id:'03',status:'complete',attempts:[{model:'A',seed:'3',generation:{imageUrl:'http://unsafe.invalid/3.webp'},qa:{qaLevel:'VISUAL'}}]},
]};
const report=buildRenderReport(state);
assert.equal(report.monetaryImageProviderCost,0);
assert.equal(report.freeOnly,true);
assert.equal(report.paidFallback,false);
assert.deepEqual(report.failedScenes,['02']);
assert.equal(report.totalScenes,3);
assert.equal(report.completedScenes,2);
assert.equal(report.modelUsage.A,2);
assert.equal(report.modelUsage.B,1);
assert.deepEqual(buildExportManifest(state).assets,[{sceneId:'01',fileName:'Scene_01.webp',url:'https://example.invalid/1.webp'}]);
console.log('IMAGE_RENDER_V2_EXPORT_TEST=PASS');
