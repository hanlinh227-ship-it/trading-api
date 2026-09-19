import assert from 'node:assert/strict';
import {
  BYBIT_AI_LEGION_ROLES,
  BYBIT_AI_LEGION_VERSION,
  bybitAiLegionPolicy,
  evaluateBybitAiLegionAgents,
} from './bybit-ai-legion.js';

assert.equal(BYBIT_AI_LEGION_VERSION,'BYBIT_AI_LEGION_V4_SINGLE_EXECUTOR_RESEARCH_SWARM');
assert.deepEqual(BYBIT_AI_LEGION_ROLES.map(x=>x.id),[
  'macro_news_agent',
  'market_structure_flow_agent',
  'order_risk_architect_agent',
  'independent_adversarial_checker',
]);
assert.equal(BYBIT_AI_LEGION_ROLES.filter(x=>x.required).length,1);
assert.equal(BYBIT_AI_LEGION_ROLES.filter(x=>x.executionAuthority===true).length,1);
assert.equal(BYBIT_AI_LEGION_ROLES.find(x=>x.executionAuthority===true).id,'order_risk_architect_agent');
assert.equal(BYBIT_AI_LEGION_ROLES.filter(x=>x.researchOnly===true).length,3);

const agent=(roleId,{verdict='SUPPORT',confidence=.8,riskMultiplier=1,ok=true,executionAction=null}={})=>({
  roleId,
  required:roleId==='order_risk_architect_agent',
  ok,
  verdict,
  side:'BUY',
  confidence,
  riskMultiplier,
  reasons:[],
  freshnessOk:true,
  executionAction,
  executionAuthority:roleId==='order_risk_architect_agent',
  researchOnly:roleId!=='order_risk_architect_agent',
});

let out=evaluateBybitAiLegionAgents([
  agent('macro_news_agent',{verdict:'VETO',confidence:.82}),
  agent('market_structure_flow_agent',{verdict:'VETO',confidence:.76}),
  agent('independent_adversarial_checker',{verdict:'VETO',confidence:.74}),
  agent('order_risk_architect_agent',{verdict:'SUPPORT',executionAction:'OPEN',confidence:.71,riskMultiplier:.7}),
]);
assert.equal(out.approved,true);
assert.equal(out.reason,'SOLE_AI_EXECUTOR_OPEN_AUTHORIZED');
assert.equal(out.executionAction,'OPEN');
assert.equal(out.riskMultiplier,.7);
assert.equal(out.confidenceFloor,.71);

out=evaluateBybitAiLegionAgents([
  agent('macro_news_agent',{verdict:'SUPPORT'}),
  agent('market_structure_flow_agent',{verdict:'SUPPORT'}),
  agent('order_risk_architect_agent',{verdict:'SUPPORT',executionAction:'HOLD'}),
]);
assert.equal(out.approved,false);
assert.equal(out.reason,'SOLE_AI_EXECUTOR_HOLD');
assert.equal(out.executionAction,'HOLD');

out=evaluateBybitAiLegionAgents([
  agent('macro_news_agent',{verdict:'SUPPORT'}),
  agent('market_structure_flow_agent',{verdict:'SUPPORT'}),
  agent('order_risk_architect_agent',{verdict:'SUPPORT',executionAction:'CLOSE'}),
]);
assert.equal(out.approved,false);
assert.equal(out.reason,'SOLE_AI_EXECUTOR_CLOSE_AUTHORIZED');
assert.equal(out.executionAction,'CLOSE');

out=evaluateBybitAiLegionAgents([
  agent('macro_news_agent'),
  agent('market_structure_flow_agent'),
]);
assert.equal(out.approved,false);
assert.equal(out.reason,'AI_EXECUTOR_MISSING');

out=evaluateBybitAiLegionAgents([
  agent('order_risk_architect_agent',{verdict:'VETO',executionAction:'OPEN',ok:true}),
]);
assert.equal(out.approved,false);
assert.equal(out.reason,'AI_EXECUTOR_VETO');

const liveOff=bybitAiLegionPolicy({MODEL_MESH_EXECUTION_ENABLED:'1'},'LIVE');
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
assert.equal(liveOn.participationMode,'ONE_STICKY_EXECUTOR_PLUS_ROTATING_RESEARCH_SWARM_MAX4');
assert.equal(liveOn.executionModelPolicy,'ONE_STICKY_HEALTHY_EXECUTOR_FAILOVER_ONLY');
assert.equal(liveOn.researchModelPolicy,'ROTATE_ALL_OTHER_HEALTHY_MODEL_FAMILIES');
assert.equal(liveOn.alwaysDecision,true);
assert.equal(liveOn.forcedTrade,false);

const demo=bybitAiLegionPolicy({MODEL_MESH_EXECUTION_ENABLED:'1'},'DEMO');
assert.equal(demo.enabled,true);
assert.equal(demo.requiredForNewRisk,true);
assert.equal(demo.liveActivationRequired,false);

console.log('BYBIT_AI_LEGION_TEST=PASS');
