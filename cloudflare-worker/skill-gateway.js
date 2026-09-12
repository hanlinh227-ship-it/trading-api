const PROFILE_RANK={FAST:0,STANDARD:1,DEEP:2};

function normalizeText(value){
  return String(value??'').normalize('NFKC').toLocaleLowerCase('und').replace(/\s+/g,' ').trim();
}

function contains(text,needle){
  return needle!==''&&text.includes(needle);
}

function validSnapshot(snapshot){
  return snapshot&&snapshot.schema_version===1&&typeof snapshot.source_sha==='string'&&snapshot.skills&&snapshot.capsules&&snapshot.profiles;
}

function raiseProfile(current,next){
  return PROFILE_RANK[next]>PROFILE_RANK[current]?next:current;
}

function matchTerms(text,terms=[]){
  const hits=[];
  for(const raw of terms){
    const term=normalizeText(raw);
    if(term&&contains(text,term))hits.push(term);
  }
  return hits;
}

function candidateScore(meta,text){
  if(matchTerms(text,meta.excludes||[]).length)return null;
  const triggerHits=matchTerms(text,meta.triggers||[]);
  const aliasHits=matchTerms(text,meta.aliases||[]);
  const hits=[...triggerHits,...aliasHits];
  if(!hits.length)return null;
  const longest=Math.max(...hits.map(x=>x.length));
  const totalLength=hits.reduce((sum,x)=>sum+x.length,0);
  return {hits:hits.length,longest,totalLength,priority:Number(meta.priority||0)};
}

function compareCandidates(a,b){
  for(const key of ['hits','longest','totalLength','priority']){
    if(a.score[key]!==b.score[key])return b.score[key]-a.score[key];
  }
  return String(a.id).localeCompare(String(b.id));
}

function selectSkill(text,snapshot,trustedHints={}){
  const hintedSkill=typeof trustedHints?.skill==='string'?trustedHints.skill:'';
  const hintedDomain=typeof trustedHints?.domain==='string'?trustedHints.domain:'';
  if(hintedSkill){
    const meta=snapshot.skills[hintedSkill];
    if(meta?.primary_selectable===true&&(!hintedDomain||meta.domain===hintedDomain))return hintedSkill;
  }
  const rows=[];
  for(const [id,meta] of Object.entries(snapshot.skills)){
    if(!meta||meta.primary_selectable!==true)continue;
    if(hintedDomain&&meta.domain!==hintedDomain)continue;
    const score=candidateScore(meta,text);
    if(score)rows.push({id,score});
  }
  rows.sort(compareCandidates);
  return rows[0]?.id||snapshot.fallback_primary_skill||'core_reasoning';
}

function selectProfile(text,meta,snapshot){
  let profile='FAST';
  const fresh=matchTerms(text,snapshot.fresh_state_terms||[]).length>0;
  if(fresh)profile=raiseProfile(profile,'STANDARD');
  if(Array.isArray(meta?.tools)&&meta.tools.length)profile=raiseProfile(profile,'STANDARD');
  for(const term of snapshot.profile_escalation?.STANDARD||[]){if(contains(text,normalizeText(term)))profile=raiseProfile(profile,'STANDARD');}
  for(const term of snapshot.profile_escalation?.DEEP||[]){if(contains(text,normalizeText(term)))profile='DEEP';}
  if(meta?.domain==='trading')profile='DEEP';
  return {profile,fresh};
}

export function routeSkillRequest({text='',trustedHints={}}={},snapshot){
  const started=globalThis.performance?.now?.()??Date.now();
  if(!validSnapshot(snapshot))throw new Error('SKILL_GATEWAY_SNAPSHOT_INVALID');
  const normalized=normalizeText(text);
  const primarySkill=selectSkill(normalized,snapshot,trustedHints);
  const meta=snapshot.skills[primarySkill];
  const capsule=snapshot.capsules[primarySkill];
  if(!meta||meta.primary_selectable!==true)throw new Error('PRIMARY_SKILL_INVALID');
  if(!capsule||capsule.skill_id!==primarySkill||!capsule.capsule_hash)throw new Error('SKILL_CAPSULE_INVALID');
  const {profile,fresh}=selectProfile(normalized,meta,snapshot);
  if(!snapshot.profiles[profile])throw new Error('RUNTIME_PROFILE_INVALID');
  const tools=Array.isArray(meta.tools)?[...meta.tools]:[];
  const requiresAuthority=profile==='DEEP'||meta.domain==='trading'||Boolean(trustedHints?.projectAuthorityRequired);
  const ended=globalThis.performance?.now?.()??Date.now();
  return Object.freeze({
    profile,
    domain:meta.domain,
    primarySkill,
    capsuleId:primarySkill,
    capsuleHash:capsule.capsule_hash,
    outputContract:capsule.output_contract,
    supportingSkills:[],
    requiresFreshState:fresh||meta.domain==='trading',
    requiresAuthority,
    toolRequirement:tools,
    sourceSha:snapshot.source_sha,
    snapshotSchemaVersion:snapshot.schema_version,
    releaseId:snapshot.release_id,
    routeLatencyMs:Math.max(0,ended-started),
    externalRoutingCalls:0,
  });
}

export function assertResponseQuality({route,execution={}}={}){
  if(!route?.primarySkill)throw new Error('QUALITY_GATE_PRIMARY_SKILL_MISSING');
  if(!route?.capsuleHash)throw new Error('QUALITY_GATE_CAPSULE_MISSING');
  if(!['FAST','STANDARD','DEEP'].includes(route.profile))throw new Error('QUALITY_GATE_PROFILE_INVALID');
  if(execution.capsuleApplied!==true)throw new Error('QUALITY_GATE_CAPSULE_NOT_APPLIED');
  if(route.requiresAuthority&&execution.authorityAllowed!==true)throw new Error('QUALITY_GATE_AUTHORITY_NOT_SATISFIED');
  if(route.requiresFreshState&&execution.freshStateSatisfied!==true)throw new Error('QUALITY_GATE_FRESH_STATE_NOT_SATISFIED');
  if((route.toolRequirement?.length||0)>0&&execution.toolRequirementSatisfied!==true)throw new Error('QUALITY_GATE_TOOL_REQUIREMENT_NOT_SATISFIED');
  if(execution.answered!==true)throw new Error('QUALITY_GATE_EMPTY_ANSWER');
  return true;
}

export const _test={normalizeText,candidateScore,selectSkill,selectProfile};
