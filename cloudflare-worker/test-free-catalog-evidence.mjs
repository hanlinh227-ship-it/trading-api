// Vendor free-tier catalog as pricing evidence.
//
// NVIDIA publishes its Free Endpoint tier on a web catalog its API does not
// expose (0 of 82 rows carry any free field). So pricing evidence and liveness
// evidence come from different places, and the split has to stay visible: the
// catalog says what is free, only a completion probe says what answers, and
// neither substitutes for the other. A capture that is missing, unattested or
// past its window admits nothing.
import assert from 'node:assert/strict';
import fs from 'node:fs';

const doc = JSON.parse(fs.readFileSync('AI_SKILL_LIBRARY/v4/model_mesh/provider_free_catalogs.json', 'utf8'));

assert.equal(doc.version, 1);
assert.equal(doc.policy.authority, 'pricing_evidence_only');
assert.equal(doc.policy.is_api_evidence, false, 'a web page must never be recorded as API evidence');
assert.equal(doc.policy.liveness_authority, 'api_completion_probe');
assert.equal(doc.policy.requires_account_holder_attestation, true);
assert.ok(doc.policy.revalidate_after_days >= 1 && doc.policy.revalidate_after_days <= 365);
assert.equal(doc.policy.stale_action, 'quarantine_before_next_request');

const nvidia = doc.catalogs.nvidia_nim;
assert.ok(nvidia, 'nvidia_nim must have a catalog entry even while it is empty');
assert.equal(nvidia.source_kind, 'vendor_web_catalog');
assert.ok(nvidia.source_url.startsWith('https://'));
assert.equal(nvidia.free_tier_label, 'Free Endpoint');

// Nothing may be admitted from an uncaptured catalog. This is the state the
// entry ships in, and shipping it any other way would assert a list nobody read.
if (!nvidia.free_models.length) {
  assert.equal(nvidia.state, 'PENDING_CAPTURE');
  assert.equal(nvidia.captured_at, null);
  assert.equal(nvidia.account_holder_attestation, null);
}
// A populated capture must carry its provenance, or it is just a list.
if (nvidia.free_models.length) {
  assert.ok(nvidia.captured_at, 'a populated catalog needs a capture timestamp');
  assert.ok(nvidia.account_holder_attestation, 'a populated catalog needs the account-holder attestation');
  const ageDays = (Date.now() - Date.parse(nvidia.captured_at)) / 86400000;
  assert.ok(ageDays <= doc.policy.revalidate_after_days, `capture is stale: ${ageDays.toFixed(1)}d`);
  for (const id of nvidia.free_models) assert.equal(typeof id, 'string');
}

// Every recorded provider must exist in the provider registry, so a catalog
// cannot quietly introduce a provider that nothing else knows about.
const providers = fs.readFileSync('AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml', 'utf8');
for (const providerId of Object.keys(doc.catalogs)) {
  assert.ok(providers.includes(`\n  ${providerId}:`), `catalog provider is not registered: ${providerId}`);
}

// No credential material, ever.
const serialized = JSON.stringify(doc).toLowerCase();
for (const forbidden of ['api_key', 'authorization', 'bearer ', 'nvapi-', 'sk-']) {
  assert.equal(serialized.includes(forbidden), false, forbidden);
}

console.log('vendor free-catalog evidence contracts ok');
