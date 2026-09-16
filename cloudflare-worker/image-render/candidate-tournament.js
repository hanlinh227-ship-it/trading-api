import {normalizeCriticResult} from './critic.js';

const DEFAULT_WEIGHTS={promptAdherence:1.0,referenceFidelity:1.15,anatomy:1.0,composition:0.85,backgroundAccuracy:0.8,wardrobeAccuracy:0.9,propAccuracy:0.85,textAccuracy:1.0,styleAccuracy:0.75,continuity:1.0};
// Reference tasks are not won on overall aesthetics: fidelity to the reference, identity
// consistency and compliance with the user's explicit locks dominate the ranking.
const REFERENCE_WEIGHTS={...DEFAULT_WEIGHTS,referenceFidelity:3.0,identityConsistency:3.0,lockCompliance:2.5,wardrobeAccuracy:1.6,propAccuracy:1.5,continuity:1.4,composition:0.5,styleAccuracy:0.4};
const numberOr=(value,fallback=0)=>Number.isFinite(Number(value))?Number(value):fallback;

function candidateScore(result,weights=DEFAULT_WEIGHTS){
  const normalized=normalizeCriticResult(result);
  if(!normalized.ok)return {normalized,score:-1};
  let weighted=0,total=0;
  for(const [dimension,weight] of Object.entries(weights)){
    if(normalized.dimensions[dimension]===undefined)continue;
    weighted+=normalized.dimensions[dimension]*weight;total+=weight;
  }
  const dimensional=total?weighted/total:normalized.overallScore;
  const score=dimensional*0.7+normalized.overallScore*0.25+normalized.confidence*100*0.05;
  return {normalized,score:Number(score.toFixed(4))};
}

export function selectBestCandidate({candidates=[],criticResults={},thresholds={},referenceTask=false,weights}={}){
  if(!Array.isArray(candidates)||candidates.length===0)throw new Error('candidate_required');
  const activeWeights=weights||(referenceTask?REFERENCE_WEIGHTS:DEFAULT_WEIGHTS);
  const passThreshold=numberOr(thresholds.pass,85);
  const referenceThreshold=thresholds.referenceFidelity===undefined?null:numberOr(thresholds.referenceFidelity,0);
  const lockThreshold=thresholds.lockCompliance===undefined?null:numberOr(thresholds.lockCompliance,0);
  const ranked=candidates.map(candidate=>{
    const result=criticResults instanceof Map?criticResults.get(candidate.id):criticResults?.[candidate.id];
    const evaluated=candidateScore(result,activeWeights);
    const dimensions=evaluated.normalized.dimensions||{};
    const unverifiedReasons=[];
    if(!evaluated.normalized.ok)unverifiedReasons.push('visual_critic_unavailable');
    else if(evaluated.normalized.overallScore<passThreshold)unverifiedReasons.push('overall_score_below_threshold');
    for(const dimension of referenceTask?['referenceFidelity','identityConsistency']:[]){
      // A reference task is never reported verified on evidence the critic did not produce.
      if(dimensions[dimension]===undefined)unverifiedReasons.push(`${dimension==='referenceFidelity'?'reference_fidelity':'identity_consistency'}_not_evaluated`);
      else if(referenceThreshold!==null&&dimensions[dimension]<referenceThreshold)unverifiedReasons.push(`${dimension==='referenceFidelity'?'reference_fidelity':'identity_consistency'}_below_threshold`);
    }
    if(!referenceTask&&referenceThreshold!==null&&dimensions.referenceFidelity!==undefined&&dimensions.referenceFidelity<referenceThreshold)unverifiedReasons.push('reference_fidelity_below_threshold');
    if(lockThreshold!==null&&dimensions.lockCompliance!==undefined&&dimensions.lockCompliance<lockThreshold)unverifiedReasons.push('lock_compliance_below_threshold');
    const passed=unverifiedReasons.length===0;
    return {...candidate,critic:evaluated.normalized,tournamentScore:evaluated.score,passed,verified:passed,unverifiedReasons};
  }).sort((a,b)=>b.tournamentScore-a.tournamentScore||String(a.id).localeCompare(String(b.id)));
  const passing=ranked.find(candidate=>candidate.passed);
  const selected=passing||ranked[0];
  return {selected,ranked,passed:Boolean(passing),verified:Boolean(passing?.verified)};
}

export {DEFAULT_WEIGHTS as CANDIDATE_TOURNAMENT_WEIGHTS,REFERENCE_WEIGHTS as CANDIDATE_TOURNAMENT_REFERENCE_WEIGHTS};
