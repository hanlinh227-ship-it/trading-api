function candidateKey(model){return `${String(model?.provider_id||'')}:${String(model?.model_id||'')}`;}

export function applyCapabilityEvidence(models,activeIndex){
  const entries=Array.isArray(activeIndex?.entries)?activeIndex.entries:[];
  const byKey=new Map(entries.map(entry=>[String(entry?.candidate_key||''),entry]));
  return (Array.isArray(models)?models:[]).map(model=>{
    const entry=byKey.get(candidateKey(model));
    if(!entry)return {...model,capability_evidence:{}};
    if(String(entry.model_family||'')!==String(model?.model_family||''))return {...model,capability_evidence:{}};
    const evidence=entry.capability_evidence&&typeof entry.capability_evidence==='object'?entry.capability_evidence:{};
    return {...model,capability_evidence:evidence};
  });
}

export function enabledHardCapabilities(activeIndex,domain){
  const target=String(domain||'');
  const coverage=activeIndex?.coverage&&typeof activeIndex.coverage==='object'?activeIndex.coverage:{};
  return Object.values(coverage)
    .filter(row=>row&&typeof row==='object'&&String(row.domain||'')===target&&row.enabled===true&&row.gate_eligible===true)
    .map(row=>String(row.capability||''))
    .filter(Boolean)
    .sort();
}

export function capabilityEvidenceDiagnostics(activeIndex){
  const entries=Array.isArray(activeIndex?.entries)?activeIndex.entries:[];
  let verifiedRecords=0;
  for(const entry of entries){
    const evidence=entry?.capability_evidence&&typeof entry.capability_evidence==='object'?entry.capability_evidence:{};
    for(const row of Object.values(evidence))if(row?.state==='VERIFIED')verifiedRecords+=1;
  }
  const coverage=activeIndex?.coverage&&typeof activeIndex.coverage==='object'?activeIndex.coverage:{};
  const enabledHardGates=Object.values(coverage).filter(row=>row?.enabled===true&&row?.gate_eligible===true).length;
  return {indexLoaded:Boolean(activeIndex&&Array.isArray(activeIndex.entries)),verifiedRecords,enabledHardGates};
}
