const nowMs=()=>globalThis.performance?.now?.()??Date.now();
const normalize=value=>String(value??'').normalize('NFKC').toLocaleLowerCase('en-US').replace(/\s+/g,' ').trim();

const DEEP_PATTERNS=[
  /\b(?:live|trading|trade|market entry|quét market|quét thị trường|tìm entry)\b/u,
  /\b(?:architecture|architectural|protocol|kiến trúc|giao thức)\b/u,
  /\b(?:deploy|deployment|production|runtime|triển khai)\b/u,
  /\b(?:withdraw|transfer|payment|wallet|financial action|rút tiền|chuyển tiền|ví)\b/u,
  /\b(?:delete|destroy|drop database|wipe|xóa dữ liệu|phá hủy)\b/u,
  /\b(?:password|credential|api key|private key|mật khẩu|khóa riêng|thông tin đăng nhập)\b/u,
];
const FRESH_PATTERNS=[/\b(?:current|latest|today|now|live|real[- ]?time|hiện tại|mới nhất|hôm nay|giá live|dữ liệu live)\b/u];
const AUTHORITY_PATTERNS=[/\b(?:project|repository|repo|production|runtime|trading|trade|dự án|quỹ|tài khoản)\b/u];

function phraseMatches(text,phrase){
  const p=normalize(phrase);
  return p&&text.includes(p);
}

function candidateScore(skill,text,trustedHints={}){
  const excludes=(skill.excludes||[]).map(normalize);
  if(excludes.some(item=>item&&text.includes(item)))return null;
  const domainHint=normalize(trustedHints.domain||'');
  const skillHint=normalize(trustedHints.skill||'');
  const trustedSkill=skillHint&&skillHint===normalize(skill.id)?1:0;
  const trustedDomain=domainHint&&domainHint===normalize(skill.domain)?1:0;
  const phrases=[...(skill.triggers||[]),...(skill.aliases||[])];
  const matched=phrases.filter(p=>phraseMatches(text,p)).map(normalize);
  if(!trustedSkill&&!trustedDomain&&matched.length===0)return null;
  const specificity=matched.reduce((sum,p)=>sum+p.length,0);
  return {trustedSkill,trustedDomain,count:matched.length,specificity,priority:Number(skill.priority||0)};
}

function compareCandidates(a,b){
  for(const key of ['trustedSkill','trustedDomain','count','specificity','priority']){
    if(a.score[key]!==b.score[key])return b.score[key]-a.score[key];
  }
  return String(a.skill.id).localeCompare(String(b.skill.id));
}

function chooseProfile(text,skill){
  const deep=DEEP_PATTERNS.some(pattern=>pattern.test(text));
  const fresh=FRESH_PATTERNS.some(pattern=>pattern.test(text));
  const toolRequirement=Array.isArray(skill.tools)&&skill.tools.length>0;
  const sourceRequirement=Array.isArray(skill.sources)&&skill.sources.length>0;
  if(deep)return 'DEEP';
  if(fresh||toolRequirement||sourceRequirement)return 'STANDARD';
  return 'FAST';
}

export function routeSkillRequest({text,trustedHints={}}={},snapshot){
  const started=nowMs();
  if(!snapshot||snapshot.schema_version!==1)throw new Error('skill_gateway_invalid_snapshot');
  const normalized=normalize(text);
  if(!normalized)throw new Error('skill_gateway_text_required');
  const skills=snapshot.skills||{};
  const fallback=snapshot.fallback_primary_skill||'core_reasoning';
  if(!skills[fallback]||!snapshot.capsules?.[fallback])throw new Error('skill_gateway_fallback_unavailable');

  const ranked=[];
  for(const skill of Object.values(skills)){
    if(!skill||skill.id==='task_router')continue;
    const score=candidateScore(skill,normalized,trustedHints);
    if(score)ranked.push({skill,score});
  }
  ranked.sort(compareCandidates);
  const selected=ranked[0]?.skill||skills[fallback];
  const capsule=snapshot.capsules?.[selected.id];
  if(!capsule||!capsule.capsule_hash)throw new Error('skill_gateway_capsule_missing');
  const profile=chooseProfile(normalized,selected);
  const profileContract=snapshot.profiles?.[profile];
  if(!profileContract||profileContract.primary_skill_count!==1||profileContract.skill_capsule_required!==true)throw new Error('skill_gateway_profile_invalid');
  const requiresFreshState=FRESH_PATTERNS.some(pattern=>pattern.test(normalized))||selected.id==='live_data_validation'||selected.domain==='trading'&&/\b(?:live|hiện tại|current|market|quét)\b/u.test(normalized);
  const requiresAuthority=profile==='DEEP'||AUTHORITY_PATTERNS.some(pattern=>pattern.test(normalized));
  const toolRequirement=Array.isArray(selected.tools)&&selected.tools.length?selected.tools.slice():[];
  return {
    profile,
    domain:selected.domain,
    primarySkill:selected.id,
    capsuleId:selected.id,
    capsuleHash:capsule.capsule_hash,
    capsule,
    supportingSkills:[],
    requiresFreshState,
    requiresAuthority,
    toolRequirement,
    sourceSha:snapshot.source_sha,
    externalRoutingCalls:0,
    routeLatencyMs:Math.max(0,nowMs()-started),
  };
}

export function assertResponseQuality({route,execution}={}){
  if(!route?.primarySkill)throw new Error('quality_gate_primary_skill_missing');
  if(!route?.capsuleId||!route?.capsuleHash||!route?.capsule)throw new Error('quality_gate_capsule_missing');
  if(route.capsule.skill_id!==route.primarySkill)throw new Error('quality_gate_capsule_identity_mismatch');
  if(!execution||execution.appliedCapsuleHash!==route.capsuleHash)throw new Error('quality_gate_capsule_not_applied');
  if(typeof execution.answer!=='string'||execution.answer.trim()==='')throw new Error('quality_gate_answer_empty');
  if(route.requiresFreshState&&execution.freshStateSatisfied===false)throw new Error('quality_gate_fresh_state_required');
  if(execution.authorityViolated===true)throw new Error('quality_gate_authority_violation');
  return {ok:true};
}
