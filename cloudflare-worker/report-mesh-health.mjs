// Sanitized provider readiness matrix, read from /brain/mesh/health on stdin.
//
// Prints ids, states and counts only: never a key, a credential, a prompt or a
// provider response body. Classifies each binding into the operational states
// the mesh actually distinguishes, so "not healthy" is never conflated with
// "no credential" or "ineligible by FREE_ONLY policy".
let raw = '';
process.stdin.on('data', (d) => {raw += d;});
process.stdin.on('end', () => {
  let doc = {};
  try { doc = JSON.parse(raw); } catch { console.log('MESH_HEALTH_REPORT=unavailable'); return; }
  const providers = Array.isArray(doc.providers) ? doc.providers : [];
  if (!providers.length) { console.log('MESH_HEALTH_REPORT=empty'); return; }

  const classify = (row) => {
    const states = Array.isArray(row.states) ? row.states : [];
    if (row.liveHealthyModelCount > 0) return 'LIVE_HEALTHY';
    if (!states.length) return 'NO_ADMITTED_MODEL';
    const cats = states.map((s) => String(s.category || ''));
    const names = states.map((s) => String(s.state || ''));
    if (cats.includes('CREDENTIAL_OR_BINDING_MISSING')) return 'USER_CREDENTIAL_BLOCKED';
    if (cats.includes('FREE_ONLY_POLICY')) return 'NOT_ELIGIBLE_FREE_ONLY';
    if (names.includes('COOLDOWN')) return 'COOLDOWN';
    if (names.includes('QUARANTINED')) return 'QUARANTINED';
    if (names.includes('DEGRADED')) return 'DEGRADED';
    return names[0] || 'UNKNOWN';
  };

  const rows = providers.map((row) => {
    const states = Array.isArray(row.states) ? row.states : [];
    return {
      provider: row.providerId,
      status: classify(row),
      bindingEnabled: row.bindingEnabled === true,
      // configured is carried by admitted models. With no admitted model there
      // is nothing to carry it, so it defaults false - reporting that as
      // "absent" would wrongly blame a missing key for an empty registry.
      credential: states.length === 0 ? 'unknown' : (row.configured === true ? 'present' : 'absent'),
      eligibleModels: row.eligibleModelCount || 0,
      liveHealthyModels: row.liveHealthyModelCount || 0,
    };
  });

  const tally = rows.reduce((acc, r) => {acc[r.status] = (acc[r.status] || 0) + 1; return acc;}, {});
  console.log(`MESH_HEALTH_REPORT observed_at=${new Date().toISOString()} bindings=${rows.length} tally=${JSON.stringify(tally)}`);
  for (const r of rows) {
    console.log(
      `  ${r.provider.padEnd(34)}${r.status.padEnd(26)}`
      + `credential=${r.credential.padEnd(7)} `
      + `eligible=${r.eligibleModels} live=${r.liveHealthyModels}`,
    );
  }
  const live = rows.filter((r) => r.status === 'LIVE_HEALTHY').length;
  const blocked = rows.filter((r) => r.status === 'USER_CREDENTIAL_BLOCKED').length;
  const noModel = rows.filter((r) => r.status === 'NO_ADMITTED_MODEL').length;
  console.log(`MESH_HEALTH_SUMMARY live_healthy=${live} user_credential_blocked=${blocked} no_admitted_model=${noModel}`);
});
