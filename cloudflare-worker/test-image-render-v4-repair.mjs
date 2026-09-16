import assert from 'node:assert/strict';
import {planRepair} from './image-render/repair-planner.js';

const base={intent:{preserveRegions:['face','background'],editableRegions:['hands','shirt'],destructiveRedrawAllowed:false},capabilities:{segment:true,localEdit:true,globalEdit:true},attempts:{repair:0,total:1,repairLimit:2,totalLimit:5}};
let plan=planRepair({...base,criticResult:{ok:true,problems:[{code:'hand_anatomy',scope:'local',severity:'major',target:'left hand'}]}});
assert.equal(plan.action,'LOCAL_MASKED_EDIT');
assert.equal(plan.target,'left hand');
assert.equal(plan.requiresSegmentation,true);

plan=planRepair({...base,criticResult:{ok:true,problems:[{code:'wardrobe_mismatch',scope:'local',severity:'major',target:'shirt'}]}});
assert.equal(plan.action,'LOCAL_MASKED_EDIT');

plan=planRepair({...base,criticResult:{ok:true,problems:[{code:'background_mismatch',scope:'global',severity:'major',target:'background'}]}});
assert.equal(plan.action,'RETRY_PROMPT','preserved background must not be globally edited');

plan=planRepair({...base,criticResult:{ok:true,problems:[{code:'identity_mismatch',scope:'global',severity:'critical'}]}});
assert.equal(plan.action,'RETRY_MODEL');

plan=planRepair({...base,capabilities:{segment:false,localEdit:true,globalEdit:false},criticResult:{ok:true,problems:[{code:'hand_anatomy',scope:'local',severity:'major',target:'left hand'}]}});
assert.equal(plan.action,'RETRY_SEED');

plan=planRepair({...base,attempts:{repair:2,total:3,repairLimit:2,totalLimit:5},criticResult:{ok:true,problems:[{code:'hand_anatomy',scope:'local',severity:'major',target:'left hand'}]}});
assert.equal(plan.action,'RETRY_MODEL');

plan=planRepair({...base,attempts:{repair:1,total:5,repairLimit:2,totalLimit:5},criticResult:{ok:true,problems:[{code:'hand_anatomy',scope:'local',severity:'major',target:'left hand'}]}});
assert.equal(plan.action,'FAIL_TERMINAL');

console.log('image render v4 targeted repair contracts: PASS');
