import assert from 'node:assert/strict';
import {compileImageIntent,validateImageIntent} from './image-render/image-intent.js';

const base={
  taskType:'REFERENCE_GENERATION',
  prompt:'Max in a sunny park',
  dataClass:'CONFIDENTIAL',
  subjectCount:1,
  referenceAssets:[{id:'max-ref',dataClass:'CONFIDENTIAL'}],
  width:1280,height:720,
  explicit:{
    subjectIdentityConstraints:['same stylized monkey character'],
    wardrobeConstraints:['yellow shirt'],
    backgroundConstraints:['sunny park'],
    cameraConstraints:['medium close-up'],
  },
};

const intent=compileImageIntent(base);
assert.equal(intent.taskType,'REFERENCE_GENERATION');
assert.equal(intent.promptOriginal,'Max in a sunny park');
assert.equal(intent.subjectCount,1);
assert.deepEqual(intent.subjectIdentityConstraints,['same stylized monkey character']);
assert.deepEqual(intent.wardrobeConstraints,['yellow shirt']);
assert.deepEqual(intent.backgroundConstraints,['sunny park']);
assert.deepEqual(intent.cameraConstraints,['medium close-up']);
assert.equal(intent.privacyClass,'CONFIDENTIAL');
assert.equal(intent.target.width,1280);
assert.equal(intent.target.height,720);
assert.equal(intent.target.aspectRatio,'16:9');
assert.equal(intent.destructiveRedrawAllowed,false);
assert.deepEqual(intent.referenceAssets,[{id:'max-ref',dataClass:'CONFIDENTIAL'}]);
assert.equal(validateImageIntent(intent).ok,true);

const editIntent=compileImageIntent({
  taskType:'IMAGE_EDIT_LOCAL',
  prompt:'change only the shirt to red',
  dataClass:'INTERNAL',
  preserveRegions:['face','background'],
  editableRegions:['shirt'],
  sourceImage:{id:'source-1',dataClass:'INTERNAL'},
});
assert.equal(editIntent.privacyClass,'INTERNAL');
assert.equal(editIntent.destructiveRedrawAllowed,false);
assert.equal(validateImageIntent(editIntent).ok,true);

const conflict=compileImageIntent({
  taskType:'IMAGE_EDIT_LOCAL',prompt:'edit hand',dataClass:'PUBLIC',
  preserveRegions:['hand'],editableRegions:['hand'],sourceImage:{id:'x',dataClass:'PUBLIC'},
});
const conflictValidation=validateImageIntent(conflict);
assert.equal(conflictValidation.ok,false);
assert.ok(conflictValidation.errors.includes('preserve_edit_region_conflict'));

assert.throws(()=>compileImageIntent({taskType:'TEXT_TO_IMAGE',prompt:'two cats',dataClass:'PUBLIC',subjectCount:0}),/invalid_subject_count/);
assert.throws(()=>compileImageIntent({taskType:'REFERENCE_GENERATION',prompt:'Max',dataClass:'PUBLIC'}),/reference_assets_required/);
assert.throws(()=>compileImageIntent({taskType:'TEXT_TO_IMAGE',prompt:'',dataClass:'PUBLIC'}),/invalid_prompt/);

console.log('image render v3 intent contracts: PASS');

// Every task that edits an existing image needs that image. Accepting one without a
// source would silently turn a targeted edit into a prompt-only render.
for(const taskType of ['INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','TEXT_RENDER_EDIT','TARGETED_REPAIR']){
  assert.throws(
    ()=>compileImageIntent({prompt:'edit this',taskType,dataClass:'PUBLIC'}),
    /source_image_required/,
    `${taskType} must require a source image`,
  );
  const intent=compileImageIntent({prompt:'edit this',taskType,dataClass:'PUBLIC',sourceImage:{id:'src'}});
  assert.equal(validateImageIntent(intent).ok,true,taskType);
  assert.equal(intent.referenceAssets.length,1);
  assert.equal(intent.destructiveRedrawAllowed,false,`${taskType} must not default to a full redraw`);
}

// A source-image task that loses its reference must fail validation, never pass silently.
const strippedEdit=compileImageIntent({prompt:'edit this',taskType:'INPAINT',dataClass:'PUBLIC',sourceImage:{id:'src'}});
assert.equal(validateImageIntent({...strippedEdit,referenceAssets:[]}).ok,false);

console.log('image render v3 intent source-image contracts: PASS');
