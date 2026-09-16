// Assert on the RUNNING Worker that the admitted pool costs nothing.
//
// The zero-cost rules were proven in unit tests and in CI against the compiled
// snapshot, but never against production. A deploy that shipped a paid model,
// a finite quota with no hard stop, or a policy that quietly re-admitted a
// trial class would have passed every gate. This reads the live health payload
// and fails the deploy on any of those.
//
// Reads stdin. Prints a verdict. Never a key, never a provider payload.
let raw = '';
process.stdin.on('data', (chunk) => { raw += chunk; });
process.stdin.on('end', () => {
  let health;
  try { health = JSON.parse(raw); } catch { fail('health_payload_not_json'); return; }
  const zc = health?.zeroCost;

  if (health?.ok !== true) fail('health_not_ok');
  if (health?.mode !== 'FREE_ONLY') fail(`mode=${health?.mode}`);
  if (health?.routingAuthority !== false) fail('routing_authority_true');
  if (health?.reasoningAuthority !== false) fail('reasoning_authority_true');
  if (health?.maxParallelFast !== 0) fail(`fast_external_workers=${health?.maxParallelFast}`);
  if (!zc || typeof zc !== 'object') {
    // An older revision without the summary cannot prove zero-cost, and a
    // deploy that cannot prove it must not pass as though it had.
    fail('zero_cost_summary_missing_from_deployed_revision');
    return;
  }

  if (zc.policySchemaVersion !== 2) fail(`policy_schema_version=${zc.policySchemaVersion}`);
  if (zc.nonZeroPriceModelCount !== 0) fail(`non_zero_price_models=${zc.nonZeroPriceModelCount}`);
  if (zc.finiteQuotaWithoutHardStopCount !== 0) fail(`finite_quota_without_hard_stop=${zc.finiteQuotaWithoutHardStopCount}`);
  if (zc.zeroCostRejectedModelCount !== 0) fail(`admitted_but_zero_cost_rejected=${zc.zeroCostRejectedModelCount}`);
  if (zc.paidFallback !== 'disabled') fail(`paid_fallback=${zc.paidFallback}`);
  if (zc.autoPurchase !== false) fail('auto_purchase_enabled');
  if (Array.isArray(zc.billableStatusesAdmitted) && zc.billableStatusesAdmitted.length) {
    fail(`billable_statuses_admitted=${zc.billableStatusesAdmitted.join(',')}`);
  }
  const expected = ['account_specific', 'free_quota_hard_stop', 'recurring', 'temporary_zero_price'];
  const actual = [...(zc.eligibleStatuses || [])].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) fail(`eligible_statuses=${actual.join(',')}`);
  if (!(zc.admittedModelCount > 0)) fail('no_admitted_models');

  // A quota window that has already closed means the next call is billable.
  if (zc.nextFreeQuotaExpiryAt) {
    const expiryMs = Date.parse(zc.nextFreeQuotaExpiryAt);
    if (!Number.isFinite(expiryMs)) fail(`quota_expiry_unparseable=${zc.nextFreeQuotaExpiryAt}`);
    if (expiryMs <= Date.now()) fail(`free_quota_expired_at=${zc.nextFreeQuotaExpiryAt}`);
  }

  console.log(
    `FREE_ONLY_ZERO_COST_GUARD=PASS models=${zc.admittedModelCount} zero_price=${zc.zeroPriceModelCount} ` +
    `finite_quota=${zc.finiteQuotaModelCount} hard_stop_missing=0 paid_fallback=disabled auto_purchase=false ` +
    `next_quota_expiry=${zc.nextFreeQuotaExpiryAt || 'none'} classes=${JSON.stringify(zc.byClass)}`
  );
});

function fail(reason) {
  console.log(`FREE_ONLY_ZERO_COST_GUARD=FAIL ${reason}`);
  process.exit(2);
}
