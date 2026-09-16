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

// Resolve against this file, not the cwd: `npm run check` runs from
// cloudflare-worker/ while the registry lives at the repository root.
const repoFile = (relative) => new URL(`../${relative}`, import.meta.url);
const doc = JSON.parse(fs.readFileSync(repoFile('AI_SKILL_LIBRARY/v4/model_mesh/provider_free_catalogs.json'), 'utf8'));

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

// Nothing may be admitted from an unresolved catalog. Display names are what a
// human read off a web page; ids are what the API answers to, and until a probe
// run maps one to the other the resolved list stays empty.
assert.ok(['PENDING_CAPTURE', 'PENDING_RESOLUTION', 'RESOLVED'].includes(nvidia.state), nvidia.state);
if (nvidia.state === 'PENDING_CAPTURE') {
  assert.equal(nvidia.free_models.length, 0);
  assert.equal(nvidia.captured_at, null);
  assert.equal(nvidia.account_holder_attestation, null);
}
if (nvidia.state === 'PENDING_RESOLUTION') {
  assert.equal(nvidia.free_models.length, 0, 'no id may be admitted before a probe resolves it');
  assert.ok(nvidia.free_display_names.length > 0);
  assert.ok(nvidia.captured_at, 'a capture needs a timestamp');
  assert.ok(nvidia.account_holder_attestation, 'a capture needs the account-holder attestation');
}
assert.equal(doc.policy.display_names_are_not_api_ids, true);

// Every resolved id must cite the display name it came from and the probe run
// that resolved it, and that name must be one the capture actually recorded.
for (const id of nvidia.free_models) {
  const record = nvidia.resolved_from?.[id];
  assert.ok(record, `resolved id without provenance: ${id}`);
  assert.ok(record.display_name, `resolved id without a display name: ${id}`);
  assert.ok(record.probe_run, `resolved id without a probe run: ${id}`);
  assert.ok(nvidia.free_display_names.includes(record.display_name), `display name is not in the capture: ${id}`);
}
// A capture goes stale; past the window it admits nothing.
if (nvidia.captured_at) {
  assert.ok(nvidia.account_holder_attestation, 'a capture needs the account-holder attestation');
  const ageDays = (Date.now() - Date.parse(nvidia.captured_at)) / 86400000;
  assert.ok(ageDays <= doc.policy.revalidate_after_days, `capture is stale: ${ageDays.toFixed(1)}d`);
  for (const id of nvidia.free_models) assert.equal(typeof id, 'string');
}

// Every recorded provider must exist in the provider registry, so a catalog
// cannot quietly introduce a provider that nothing else knows about.
const providers = fs.readFileSync(repoFile('AI_SKILL_LIBRARY/v4/model_mesh/providers.yaml'), 'utf8');
for (const providerId of Object.keys(doc.catalogs)) {
  assert.ok(providers.includes(`\n  ${providerId}:`), `catalog provider is not registered: ${providerId}`);
}

// No credential material, ever.
const serialized = JSON.stringify(doc).toLowerCase();
for (const forbidden of ['api_key', 'authorization', 'bearer ', 'nvapi-', 'sk-']) {
  assert.equal(serialized.includes(forbidden), false, forbidden);
}

console.log('vendor free-catalog evidence contracts ok');
