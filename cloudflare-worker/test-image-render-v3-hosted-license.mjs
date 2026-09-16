import assert from 'node:assert/strict';
import {HOSTED_INFERENCE_LICENSES,PERMISSIVE_LICENSES,validateModelVaultEntry} from './image-render/model-vault.js';

const base={
  modelId:'demo',canonicalRepo:'org/repo',sourceRevision:'0123456789abcdef0123456789abcdef01234567',
  commercialUseEligible:true,runtimeConfigured:false,approvalStatus:'CANDIDATE',
  supportedTasks:['TEXT_TO_IMAGE'],monetaryCost:'zero',
};

// Permissive licences stay eligible for redistribution/self-hosting.
assert.ok(PERMISSIVE_LICENSES.has('Apache-2.0'));
assert.ok(PERMISSIVE_LICENSES.has('MIT'));
assert.equal(validateModelVaultEntry({...base,codeLicense:'Apache-2.0',weightsLicense:'Apache-2.0',redistributionEligible:true}).ok,true);

// A licence that permits commercial use but not free redistribution is usable only
// through a hosted provider that already licensed it, never redistributed by us.
assert.ok(HOSTED_INFERENCE_LICENSES.has('CreativeML-Open-RAIL++-M'));
assert.equal(validateModelVaultEntry({...base,codeLicense:'CreativeML-Open-RAIL++-M',weightsLicense:'CreativeML-Open-RAIL++-M',redistributionEligible:false}).ok,true);
const redistributed=validateModelVaultEntry({...base,codeLicense:'CreativeML-Open-RAIL++-M',weightsLicense:'CreativeML-Open-RAIL++-M',redistributionEligible:true});
assert.equal(redistributed.ok,false,'a non-permissive licence must not claim redistribution eligibility');
assert.ok(redistributed.errors.includes('redistribution_requires_permissive_license'));

// An unknown or non-commercial licence is rejected outright, hosted or not.
for(const license of ['NON_COMMERCIAL','FLUX-1-dev-Non-Commercial-License','','SomeLicenseNobodyChecked']){
  assert.equal(validateModelVaultEntry({...base,codeLicense:license,weightsLicense:license,redistributionEligible:false}).ok,false,license);
}
// Commercial use must still be explicit.
assert.equal(validateModelVaultEntry({...base,codeLicense:'Apache-2.0',weightsLicense:'Apache-2.0',redistributionEligible:true,commercialUseEligible:false}).ok,false);
// Cost is still a hard gate.
assert.equal(validateModelVaultEntry({...base,codeLicense:'Apache-2.0',weightsLicense:'Apache-2.0',redistributionEligible:true,monetaryCost:'unknown'}).ok,false);

console.log('image render v3 hosted licence gate contracts: PASS');
