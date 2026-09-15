const SECRET_PATTERN=/API_KEY|TOKEN|Authorization|Bearer|secret/i;
const UNAVAILABLE_STATES=new Set(['DEGRADED','COOLDOWN','QUARANTINED']);

export function validateProbeCanary(envelope,{requireHealthy=false}={}){
  if(!envelope||envelope.ok!==true||envelope.mode!=='FREE_ONLY'||envelope.routingAuthority!==false||envelope.reasoningAuthority!==false||!Array.isArray(envelope.results)||envelope.results.length===0)throw new Error('invalid_probe_envelope');
  if(SECRET_PATTERN.test(JSON.stringify(envelope)))throw new Error('unsafe_probe_output');
  if(envelope.probedProviderCount!==envelope.results.length)throw new Error('probe_count_mismatch');
  const configured=envelope.results.filter(row=>row?.configured===true);
  if(configured.length===0)throw new Error('no_configured_provider');
  for(const row of configured){
    if(row.evidencePersisted!==true)throw new Error(`probe_evidence_not_persisted:${row.providerId}`);
    if(row.ok===true&&row.state!=='LIVE_HEALTHY')throw new Error(`probe_state_mismatch:${row.providerId}`);
    if(row.ok!==true&&!UNAVAILABLE_STATES.has(row.state))throw new Error(`probe_state_mismatch:${row.providerId}`);
  }
  const healthy=configured.filter(row=>row.ok===true&&row.state==='LIVE_HEALTHY');
  if(Number(envelope.successfulProviderCount)!==healthy.length)throw new Error('successful_count_mismatch');
  if(requireHealthy&&healthy.length===0)throw new Error('no_live_healthy_provider');
  return {configuredCount:configured.length,healthyCount:healthy.length,unavailableCount:configured.length-healthy.length,healthyProviderIds:healthy.map(row=>row.providerId).sort()};
}

export function validateLiveOverlay(envelope,health){
  const expected=new Set(envelope.results.filter(row=>row?.configured===true&&row.ok===true&&row.state==='LIVE_HEALTHY').map(row=>row.providerId));
  const actual=new Set((health?.providers||[]).filter(row=>row?.active===true).map(row=>row.providerId));
  if(expected.size!==actual.size||[...expected].some(providerId=>!actual.has(providerId)))throw new Error('overlay_active_set_mismatch');
  return {activeCount:actual.size};
}
