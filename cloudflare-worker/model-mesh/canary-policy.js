import {findCredentialLeaks} from '../security/secret-scan.js';

const UNAVAILABLE_STATES=new Set(['DEGRADED','COOLDOWN','QUARANTINED']);
const KNOWN_STATES=new Set(['CONFIGURED','LIVE_HEALTHY','DEGRADED','COOLDOWN','QUARANTINED','NOT_ELIGIBLE']);

export function validateProbeCanary(envelope,{requireHealthy=false,secretValues=[]}={}){
  if(!envelope||envelope.ok!==true||envelope.mode!=='FREE_ONLY'||envelope.routingAuthority!==false||envelope.reasoningAuthority!==false||!Array.isArray(envelope.results)||envelope.results.length===0)throw new Error('invalid_probe_envelope');
  const leaks=findCredentialLeaks(JSON.stringify(envelope),{secretValues});
  if(leaks.length)throw new Error(`unsafe_probe_output:${leaks.map(leak=>`${leak.kind}:${leak.detail}`).sort().join(',')}`);
  if(envelope.probedProviderCount!==envelope.results.length)throw new Error('probe_count_mismatch');
  // "This probe call succeeded" and "the mesh now holds live-healthy evidence"
  // are two different facts. They coincide almost always, and the deploy canary
  // broke precisely in the case where they did not: a concurrent probe's newer
  // observation had already won, so a successful call no longer described what
  // the mesh would read. They are counted separately from here on.
  const configured=envelope.results.filter(row=>row?.configured===true);
  if(configured.length===0)throw new Error('no_configured_provider');
  for(const row of configured){
    if(row.evidencePersisted!==true)throw new Error(`probe_evidence_not_persisted:${row.providerId}`);
    if(row.superseded===true){
      // A superseded row reports OUR probe result alongside the state a NEWER
      // observation persisted, so the two are legitimately decoupled. The state
      // must still be a real health state - decoupled is not unconstrained.
      if(!KNOWN_STATES.has(String(row.state)))throw new Error(`probe_state_unknown:${row.providerId}`);
      continue;
    }
    if(row.ok===true&&row.state!=='LIVE_HEALTHY')throw new Error(`probe_state_mismatch:${row.providerId}`);
    if(row.ok!==true&&!UNAVAILABLE_STATES.has(row.state))throw new Error(`probe_state_mismatch:${row.providerId}`);
  }
  const succeeded=configured.filter(row=>row.ok===true);
  const healthy=configured.filter(row=>row.ok===true&&row.state==='LIVE_HEALTHY');
  if(Number(envelope.successfulProviderCount)!==succeeded.length)throw new Error('successful_count_mismatch');
  // An envelope that reports the live-healthy count must report it correctly.
  // An envelope that does not report it at all is an older shape, where the two
  // counts were one field; hold that shape to the stricter original rule rather
  // than letting a missing field buy a weaker check.
  if(envelope.liveHealthyProviderCount===undefined){
    if(Number(envelope.successfulProviderCount)!==healthy.length)throw new Error('live_healthy_count_mismatch');
  }else if(Number(envelope.liveHealthyProviderCount)!==healthy.length){
    throw new Error('live_healthy_count_mismatch');
  }
  if(requireHealthy&&healthy.length===0)throw new Error('no_live_healthy_provider');
  return {configuredCount:configured.length,healthyCount:healthy.length,succeededCount:succeeded.length,supersededCount:configured.filter(row=>row.superseded===true).length,unavailableCount:configured.length-healthy.length,healthyProviderIds:healthy.map(row=>row.providerId).sort()};
}

export function validateLiveOverlay(envelope,health){
  const expectedProviderIds=envelope.results
    .filter(row=>row?.configured===true&&row.ok===true&&row.state==='LIVE_HEALTHY')
    .map(row=>row.providerId)
    .sort();
  const actualProviderIds=(health?.providers||[])
    .filter(row=>row?.active===true)
    .map(row=>row.providerId)
    .sort();
  const actual=new Set(actualProviderIds);
  const missingExpectedProviderIds=expectedProviderIds.filter(providerId=>!actual.has(providerId));
  if(missingExpectedProviderIds.length){
    throw new Error(`overlay_missing_expected_provider:${missingExpectedProviderIds.join(',')}`);
  }
  const expected=new Set(expectedProviderIds);
  const extraActiveProviderIds=actualProviderIds.filter(providerId=>!expected.has(providerId));
  return {
    activeCount:actualProviderIds.length,
    expectedProviderIds,
    extraActiveProviderIds,
  };
}
