import assert from 'node:assert/strict';
import {createImageProviderMesh,filterEligibleProviderModels,validateProviderModelRegistration} from './image-render/provider-mesh.js';

const aiHorde={providerId:'ai_horde',modelId:'sdxl',monetaryCost:'zero',paidFallback:false,autoPurchase:false,supportedDataClasses:['PUBLIC'],referenceSafe:false,supportedTasks:['TEXT_TO_IMAGE'],health:'healthy',maxResolution:{width:1536,height:1536}};
const safeRef={providerId:'safe_free',modelId:'qwen-edit',monetaryCost:'zero',paidFallback:false,autoPurchase:false,supportedDataClasses:['PUBLIC','INTERNAL','CONFIDENTIAL'],referenceSafe:true,supportedTasks:['TEXT_TO_IMAGE','REFERENCE_GENERATION','IMAGE_EDIT_LOCAL'],health:'healthy',maxResolution:{width:2048,height:2048}};
const paid={...safeRef,providerId:'paid',monetaryCost:'paid'};
const unknownCost={...safeRef,providerId:'unknown',monetaryCost:'unknown'};
const autoPurchase={...safeRef,providerId:'auto',autoPurchase:true};

assert.equal(validateProviderModelRegistration(aiHorde).ok,true);
assert.equal(validateProviderModelRegistration(safeRef).ok,true);
assert.equal(validateProviderModelRegistration(paid).ok,false);
assert.equal(validateProviderModelRegistration(unknownCost).ok,false);
assert.equal(validateProviderModelRegistration(autoPurchase).ok,false);

const publicIntent={taskType:'TEXT_TO_IMAGE',privacyClass:'PUBLIC',referenceAssets:[],target:{width:1024,height:1024}};
const publicEligible=filterEligibleProviderModels(publicIntent,[aiHorde,safeRef,paid,unknownCost,autoPurchase]);
assert.deepEqual(publicEligible.map(x=>x.providerId).sort(),['ai_horde','safe_free']);

const privateRefIntent={taskType:'REFERENCE_GENERATION',privacyClass:'CONFIDENTIAL',referenceAssets:[{id:'ref'}],target:{width:1024,height:1024}};
const privateEligible=filterEligibleProviderModels(privateRefIntent,[aiHorde,safeRef]);
assert.deepEqual(privateEligible.map(x=>x.providerId),['safe_free']);

const mesh=createImageProviderMesh({extraRegistrations:[safeRef]});
assert.ok(mesh.listRegistrations().some(x=>x.providerId==='ai_horde'));
assert.ok(mesh.listRegistrations().some(x=>x.providerId==='safe_free'));
assert.equal(mesh.getRegistration('ai_horde','sdxl').referenceSafe,false);

console.log('image render v3 provider mesh contracts: PASS');
