import assert from 'node:assert/strict';
import {createUniversalEntryHandler} from './universal-entry-handler.js';
import {routeSkillRequest} from './skill-gateway.js';

const snapshot={
  schema_version:1,source_sha:'c'.repeat(40),release_id:'4.10.1',generated_at:'2026-09-16T00:00:00Z',fallback_primary_skill:'core_reasoning',
  presentation:{locale:'vi',mode:'plain',hide_internal_ids:true,no_underscore_display_names:true},
  profiles:{FAST:{primary_skill_count:1,skill_capsule_required:true},STANDARD:{primary_skill_count:1,skill_capsule_required:true},DEEP:{primary_skill_count:1,skill_capsule_required:true}},
  domains:{core:['core_reasoning'],writing:['advertising_copy'],trading:['trading_router']},
  skills:{
    core_reasoning:{id:'core_reasoning',display_name:'Giải thích',domain:'core',aliases:['giải thích'],triggers:['explain'],excludes:[],priority:80,tools:[],primary_selectable:true},
    advertising_copy:{id:'advertising_copy',display_name:'Viết quảng cáo',domain:'writing',aliases:['viết quảng cáo'],triggers:['ad copy'],excludes:[],priority:80,tools:[],primary_selectable:true},
    trading_router:{id:'trading_router',display_name:'Phân tích giao dịch',domain:'trading',aliases:['giao dịch'],triggers:['trading'],excludes:[],priority:90,tools:[],primary_selectable:true},
  },
  capsules:{
    core_reasoning:{skill_id:'core_reasoning',domain:'core',output_contract:'Explain precisely.',permissions:['read_only'],risk_ceiling:'read_only',capsule_hash:'core-hash'},
    advertising_copy:{skill_id:'advertising_copy',domain:'writing',output_contract:'Write advertising copy.',permissions:['read_only'],risk_ceiling:'read_only',capsule_hash:'ad-hash'},
    trading_router:{skill_id:'trading_router',domain:'trading',output_contract:'Research trading.',permissions:['read_only'],risk_ceiling:'financial',capsule_hash:'trade-hash'},
  },
  profile_escalation:{STANDARD:['project'],DEEP:['deploy','production','live','trading','giao dịch']},fresh_state_terms:['hiện tại','live'],hashes:{router:'r',runtime:'u'}
};
const env={BRAIN_CLIENT_CHATGPT_TOKEN:'cg',BRAIN_CLIENT_CLAUDE_TOKEN:'cl',BRAIN_CLIENT_GEMINI_TOKEN:'gm'};
const handler=createUniversalEntryHandler({snapshot,routeSkill:({text})=>routeSkillRequest({text},snapshot)});
function request(client,token,body,path='/brain/universal/route',method='POST'){
  return new Request(`https://example.test${path}`,{method,headers:{'x-brain-client':client,authorization:`Bearer ${token}`,'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
}

for(const [client,token] of [['chatgpt','cg'],['claude','cl'],['gemini','gm']]){
  const res=await handler(request(client,token,{text:'viết quảng cáo giày',request_id:`r-${client}`,session_id:'s1'}),env,{});
  assert.equal(res.status,200);
  const body=await res.json();
  assert.equal(body.ok,true);
  assert.equal(body.route.primarySkill,'advertising_copy');
  assert.equal(body.profile,'FAST');
  assert.equal(body.onlineBrainRequired,false);
  assert.equal(body.clientId,client);
  assert.equal('chainOfThought' in body,false);
}

let res=await handler(request('chatgpt','cg',{text:'giao dịch BTC live',request_id:'r-live',session_id:'s1',freshness:'live'}),env,{});
let body=await res.json();
assert.equal(res.status,200);
assert.equal(body.profile,'DEEP');
assert.equal(body.onlineBrainRequired,true);
assert.equal(body.safeDegradedAllowed,false);
assert.equal(body.route.primarySkill,'trading_router');

res=await handler(request('chatgpt','bad',{text:'hello',request_id:'r-bad',session_id:'s1'}),env,{});
assert.equal(res.status,401);
body=await res.json();
assert.equal(JSON.stringify(body).includes('bad'),false);

res=await handler(request('chatgpt','cg',undefined,'/brain/universal/health','GET'),env,{});
assert.equal(res.status,200);
body=await res.json();
assert.equal(body.ok,true);
assert.equal(body.brainAuthority,'GITHUB_BRAIN_V4');
assert.equal(body.fastZeroRtt,true);

res=await handler(new Request('https://example.test/not-universal'),env,{});
assert.equal(res,null);

console.log('UNIVERSAL_ENTRY_HANDLER_TESTS=PASS');
