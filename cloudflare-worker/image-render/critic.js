const clamp=(value,min,max)=>Math.min(max,Math.max(min,Number(value)));
const numberOr=(value,fallback=0)=>Number.isFinite(Number(value))?Number(value):fallback;
const normalizeSeverity=value=>['minor','major','critical','terminal'].includes(String(value||'').toLowerCase())?String(value).toLowerCase():'major';
const normalizeScope=value=>String(value||'').toLowerCase()==='local'?'local':'global';

export function normalizeCriticResult(result){
  if(!result||result.ok!==true)return {ok:false,overallScore:null,confidence:null,dimensions:{},problems:[],regions:[],rawAvailable:Boolean(result)};
  const dimensions={};
  for(const [key,value] of Object.entries(result.dimensions||{})){
    if(Number.isFinite(Number(value)))dimensions[key]=clamp(value,0,100);
  }
  return {
    ok:true,
    overallScore:clamp(numberOr(result.overallScore,0),0,100),
    confidence:clamp(numberOr(result.confidence,0),0,1),
    dimensions,
    problems:Array.isArray(result.problems)?result.problems.map(problem=>({code:String(problem?.code||'unknown_problem'),scope:normalizeScope(problem?.scope),severity:normalizeSeverity(problem?.severity),target:problem?.target?String(problem.target):null})):[],
    regions:Array.isArray(result.regions)?result.regions:[],
  };
}

export function decideQualityAction(result,{passThreshold=85,strictVisual=true}={}){
  const normalized=normalizeCriticResult(result);
  if(!normalized.ok)return {decision:'PASS_UNVERIFIED',verified:false,reasons:['visual_critic_unavailable'],critic:normalized};
  const terminal=normalized.problems.find(problem=>problem.severity==='terminal'||problem.code==='unsafe_or_invalid_output');
  if(terminal)return {decision:'FAIL_TERMINAL',verified:false,reasons:[terminal.code],critic:normalized};
  const identity=normalized.problems.find(problem=>problem.code==='identity_mismatch'||problem.code==='model_mismatch');
  if(identity)return {decision:'RETRY_MODEL',verified:false,reasons:[identity.code],critic:normalized};
  const prompt=normalized.problems.find(problem=>['prompt_mismatch','wrong_subject_count','missing_required_object'].includes(problem.code));
  if(prompt)return {decision:'RETRY_PROMPT',verified:false,reasons:[prompt.code],critic:normalized};
  const local=normalized.problems.find(problem=>problem.scope==='local'&&['major','critical'].includes(problem.severity));
  if(local)return {decision:'REPAIR_LOCAL',verified:false,reasons:[local.code],critic:normalized};
  const globalProblem=normalized.problems.find(problem=>problem.scope==='global'&&['major','critical'].includes(problem.severity));
  if(globalProblem)return {decision:'REPAIR_GLOBAL',verified:false,reasons:[globalProblem.code],critic:normalized};
  if(normalized.overallScore>=Number(passThreshold))return {decision:'PASS',verified:true,reasons:[],critic:normalized};
  return {decision:strictVisual?'RETRY_SEED':'PASS_UNVERIFIED',verified:!strictVisual,reasons:['quality_below_threshold'],critic:normalized};
}
