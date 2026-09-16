import {normalizeCriticResult} from './critic.js';

const DEFAULT_WEIGHTS={promptAdherence:1.0,referenceFidelity:1.15,anatomy:1.0,composition:0.85,backgroundAccuracy:0.8,wardrobeAccuracy:0.9,propAccuracy:0.85,textAccuracy:1.0,styleAccuracy:0.75,continuity:1.0};
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

export function selectBestCandidate({candidates=[],criticResults={},thresholds={},weights=DEFAULT_WEIGHTS}={}){
  if(!Array.isArray(candidates)||candidates.length===0)throw new Error('candidate_required');
  const passThreshold=numberOr(thresholds.pass,85);
  const referenceThreshold=thresholds.referenceFidelity===undefined?null:numberOr(thresholds.referenceFidelity,0);
  const ranked=candidates.map(candidate=>{
    const result=criticResults instanceof Map?criticResults.get(candidate.id):criticResults?.[candidate.id];
    const evaluated=candidateScore(result,weights);
    const ref=evaluated.normalized.dimensions?.referenceFidelity;
    const referencePass=referenceThreshold===null||ref===undefined||ref>=referenceThreshold;
    const passed=evaluated.normalized.ok&&evaluated.normalized.overallScore>=passThreshold&&referencePass;
    return {...candidate,critic:evaluated.normalized,tournamentScore:evaluated.score,passed,verified:passed};
  }).sort((a,b)=>b.tournamentScore-a.tournamentScore||String(a.id).localeCompare(String(b.id)));
  const passing=ranked.find(candidate=>candidate.passed);
  const selected=passing||ranked[0];
  return {selected,ranked,passed:Boolean(passing),verified:Boolean(passing?.verified)};
}

export {DEFAULT_WEIGHTS as CANDIDATE_TOURNAMENT_WEIGHTS};
