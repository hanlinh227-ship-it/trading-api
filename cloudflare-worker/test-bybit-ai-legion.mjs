import assert from 'node:assert/strict';
import {
  BYBIT_AI_LEGION_ROLES,
  BYBIT_AI_LEGION_VERSION,
  bybitAiLegionPolicy,
  evaluateBybitAiLegionAgents,
} from './bybit-ai-legion.js';

assert.equal(BYBIT_AI_LEGION_VERSION,'BYBIT_AI_LEGION_V3_ROLE_FEDERATION');
assert.deepEqual(BYBIT_AI_LEGION_ROLES.map(x=>x.id),[
  'macro_news_agent',
  'market_structure_flow_agent',
  'order_risk_architect_agent',
  'independent_adversarial_checker',
]);
assert.equal(BYBIT_AI_LEGION_ROLES.filter(x=>x.required).length,3);

const support=(roleId,{verdict='SUPPORT',confidence=.8,riskMultiplier=1,ok=true}={})=>({
  roleId,required:roleId!=='independent_adversarial_checker',ok,verdict,side:'BUY',
  confidence,riskMultiplier,reasons:[],freshnessOk:true,
});

let out=evaluateBybitAiLegionAgents([
  support('macro_news_agent',{confidence:.82,riskMultiplier:.9}),
  support('market_structure_flow_agent',{confidence:.76,riskMultiplier:.8}),
  support('order_risk_architect_agent',{verdict:'SUPPORT',confidence:.71,riskMultiplier:.7}),
  support('independent_adversarial_checker',{verdict:'NEUTRAL',confidence:.74,riskMultiplier:.85}),
]);
assert.equal(out.approved,true);
assert.equal(out.reason,'AI_LEGION_ROLE_CONTRACTS_PASS');
assert.equal(out.riskMultiplier,.7);
assert.equal(out.confidenceFloor,.71);

out=evaluateBybitAiLegionAgents([
  support('macro_news_agent'),
  support('market_structure_flow_agent',{verdict:'VETO'}),
  support('order_risk_architect_agent',{verdict:'NEUTRAL'}),
]);
assert.equal(out.approved,false);
assert.match(out.reason,/MARKET_STRUCTURE_FLOW_AGENT_VETO/);

out=evaluateBybitAiLegionAgents([
  support('macro_news_agent'),
  support('market_structure_flow_agent'),
  support('order_risk_architect_agent',{verdict:'SUPPORT'}),
  support('independent_adversarial_checker',{verdict:'VETO'}),
]);
assert.equal(out.approved,false);
assert.equal(out.reason,'AI_LEGION_ADVERSARIAL_CHECKER_VETO');

out=evaluateBybitAiLegionAgents([
  support('macro_news_agent',{riskMultiplier:1}),
  support('market_structure_flow_agent',{riskMultiplier:1}),
  support('order_risk_architect_agent',{verdict:'SUPPORT',riskMultiplier:1}),
]);
assert.equal(out.approved,true);
assert.equal(out.riskMultiplier,1);

out=evaluateBybitAiLegionAgents([
  support('macro_news_agent'),
  support('order_risk_architect_agent',{verdict:'SUPPORT'}),
]);
assert.equal(out.approved,false);
assert.equal(out.reason,'AI_LEGION_REQUIRED_ROLE_MISSING');

const liveOff=bybitAiLegionPolicy({
  MODEL_MESH_EXECUTION_ENABLED:'1',
},'LIVE');
assert.equal(liveOff.enabled,false);
assert.equal(liveOff.requiredForNewRisk,true);
assert.equal(liveOff.liveActivationRequired,true);
assert.equal(liveOff.liveActivationPresent,false);

const liveOn=bybitAiLegionPolicy({
  MODEL_MESH_EXECUTION_ENABLED:'1',
  BYBIT_AI_LEGION_LIVE_ENABLED:'true',
},'LIVE');
assert.equal(liveOn.enabled,true);
assert.equal(liveOn.modelMeshEnabled,true);
assert.equal(liveOn.minimumRequiredWorkers,3);
assert.equal(liveOn.maxWorkers,4);
assert.equal(liveOn.participationMode,'ROTATING_ALL_HEALTHY_DISTINCT_MODEL_FAMILIES_MAX4_CONCURRENT');
assert.equal(liveOn.alwaysDecision,true);
assert.equal(liveOn.forcedTrade,false);

const demo=bybitAiLegionPolicy({
  MODEL_MESH_EXECUTION_ENABLED:'1',
},'DEMO');
assert.equal(demo.enabled,true);
assert.equal(demo.requiredForNewRisk,true);
assert.equal(demo.liveActivationRequired,false);

console.log('BYBIT_AI_LEGION_TEST=PASS');
