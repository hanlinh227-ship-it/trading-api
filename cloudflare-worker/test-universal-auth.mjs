import assert from 'node:assert/strict';
import {authenticateAdapter,requiredScopeForPath,UNIVERSAL_ADAPTER_SOURCE_SHA,UNIVERSAL_CLIENT_IDS,UNIVERSAL_INTERNAL_CLIENT_IDS,UNIVERSAL_USER_CLIENT_IDS} from './universal-auth.js';

const env={
  BRAIN_CLIENT_CHATGPT_TOKEN:'chatgpt-token',
  BRAIN_CLIENT_CLAUDE_TOKEN:'claude-token',
  BRAIN_CLIENT_GEMINI_TOKEN:'gemini-token',
  BRAIN_EVERGREEN_TOKEN:'evergreen-token',
};

function req(client,token,path='/brain/universal/route',method='POST'){
  return new Request(`https://example.test${path}`,{method,headers:{'x-brain-client':client,authorization:`Bearer ${token}`}});
}

assert.match(UNIVERSAL_ADAPTER_SOURCE_SHA,/^[0-9a-f]{40}$/);
assert.deepEqual([...UNIVERSAL_CLIENT_IDS].sort(),['chatgpt','claude','evergreen','gemini']);
assert.deepEqual([...UNIVERSAL_USER_CLIENT_IDS].sort(),['chatgpt','claude','gemini']);
assert.deepEqual([...UNIVERSAL_INTERNAL_CLIENT_IDS].sort(),['evergreen']);

let out=await authenticateAdapter(req('chatgpt','chatgpt-token'),env,'brain.route');
assert.equal(out.ok,true);
assert.equal(out.principal.clientId,'chatgpt');
assert.equal(out.principal.principalType,'user');
assert.ok(out.principal.scopes.includes('brain.route'));
assert.equal('token' in out.principal,false);

out=await authenticateAdapter(req('claude','claude-token'),env,'brain.route');
assert.equal(out.ok,true);
assert.equal(out.principal.clientId,'claude');

out=await authenticateAdapter(req('gemini','gemini-token'),env,'brain.route');
assert.equal(out.ok,true);
assert.equal(out.principal.clientId,'gemini');

out=await authenticateAdapter(req('evergreen','evergreen-token','/brain/memory/review'),env,'brain.review_candidate_memory');
assert.equal(out.ok,true);
assert.equal(out.principal.principalType,'internal');
assert.equal(out.principal.scopes.includes('brain.route'),false);

out=await authenticateAdapter(req('evergreen','evergreen-token'),env,'brain.route');
assert.equal(out.ok,false);
assert.equal(out.status,403);

out=await authenticateAdapter(req('chatgpt','chatgpt-token'),env,'brain.request_deploy_action');
assert.equal(out.ok,false);
assert.equal(out.status,403);
assert.equal(out.error,'scope_denied');

out=await authenticateAdapter(req('chatgpt','wrong-token'),env,'brain.route');
assert.equal(out.ok,false);
assert.equal(out.status,401);
assert.equal(JSON.stringify(out).includes('wrong-token'),false);
assert.equal(JSON.stringify(out).includes('chatgpt-token'),false);

out=await authenticateAdapter(req('unknown','whatever'),env,'brain.route');
assert.equal(out.ok,false);
assert.equal(out.status,401);

out=await authenticateAdapter(new Request('https://example.test/brain/universal/route',{method:'POST'}),env,'brain.route');
assert.equal(out.ok,false);
assert.equal(out.status,401);

assert.equal(requiredScopeForPath('/brain/universal/route','POST'),'brain.route');
assert.equal(requiredScopeForPath('/brain/universal/health','GET'),'brain.read_runtime_health');
assert.equal(requiredScopeForPath('/brain/memory/candidates','POST'),'brain.submit_candidate_memory');
assert.equal(requiredScopeForPath('/brain/memory/review','POST'),'brain.review_candidate_memory');
assert.equal(requiredScopeForPath('/brain/context/query','POST'),'brain.read_context');
assert.equal(requiredScopeForPath('/brain/unknown','GET'),null);

console.log('UNIVERSAL_AUTH_TESTS=PASS');
