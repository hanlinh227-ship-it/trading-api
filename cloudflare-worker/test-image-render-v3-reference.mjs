import assert from 'node:assert/strict';
import {createReferenceProfile,validateReferenceRoute} from './image-render/reference-profile.js';

const profile=createReferenceProfile({references:[{id:'max-ref',dataClass:'CONFIDENTIAL'}],constraints:{characterClass:'stylized monkey',headShape:'round',bodyProportions:'childlike',palette:['brown fur','cream face'],eyeStyle:'large cartoon eyes',clothing:['yellow shirt'],accessories:['blue backpack'],recurringProps:['red ball'],silhouette:'small monkey child',forbiddenDeviations:['no wardrobe change','no extra limbs'],sceneInvariantFeatures:['fur palette','face shape','shirt']}});
assert.equal(profile.profileVersion,'reference_profile_v3');
assert.equal(profile.referenceCount,1);
assert.equal(profile.characterClass,'stylized monkey');
assert.deepEqual(profile.clothing,['yellow shirt']);
assert.ok(profile.sceneInvariantFeatures.includes('shirt'));
assert.equal(profile.biometricIdentityClaim,false);

const intent={taskType:'REFERENCE_GENERATION',privacyClass:'CONFIDENTIAL',referenceAssets:[{id:'max-ref'}],target:{width:1024,height:1024}};
const aiHorde={providerId:'ai_horde',modelId:'sdxl',monetaryCost:'zero',paidFallback:false,autoPurchase:false,supportedDataClasses:['PUBLIC'],supportedTasks:['TEXT_TO_IMAGE'],referenceSafe:false,maxResolution:{width:1536,height:1536}};
const safe={providerId:'safe',modelId:'edit',monetaryCost:'zero',paidFallback:false,autoPurchase:false,supportedDataClasses:['PUBLIC','CONFIDENTIAL'],supportedTasks:['REFERENCE_GENERATION'],referenceSafe:true,maxResolution:{width:2048,height:2048}};
assert.equal(validateReferenceRoute({intent,providerModel:aiHorde}).ok,false);
assert.equal(validateReferenceRoute({intent,providerModel:safe}).ok,true);
const unavailable=validateReferenceRoute({intent,providerModel:null});
assert.equal(unavailable.ok,false);
assert.equal(unavailable.state,'WAITING_FOR_SAFE_FREE_RUNTIME');
assert.equal(validateReferenceRoute({intent,providerModel:{...safe,monetaryCost:'paid'}}).ok,false);

console.log('image render v3 reference contracts: PASS');
