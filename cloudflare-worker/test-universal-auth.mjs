import assert from 'node:assert/strict';
import {authenticateAdapter,requiredScopeForPath} from './universal-auth.js';

const env={
  BRAIN_CLIENT_CHATGPT_TOKEN:'chatgpt-token',
  BRAIN_CLIENT_CLAUDE_TOKEN:'claude-token',
  BRAIN_CLIENT_GEMINI_TOKEN:'gemini-token',
};

function req(client,token,path='/brain/universal/route',method='POST'){
  return new Request(`https://example.test${path}`,{method,headers:{'x-brain-client':client,authorization:`Bearer ${token}`}});
}

let out=await authenticateAdapter(req('chatgpt','chatgpt-token'),env,'brain.route');
assert.equal(out.ok,true);
assert.equal(out.principal.clientId,'chatgpt');
assert.ok(out.principal.scopes.includes('brain.route'));
assert.equal('token' in out.principal,false);

out=await authenticateAdapter(req('claude','claude-token'),env,'brain.route');
assert.equal(out.ok,true);
assert.equal(out.principal.clientId,'claude');

out=await authenticateAdapter(req('gemini','gemini-token'),env,'brain.route');
assert.equal(out.ok,true);
assert.equal(out.principal.clientId,'gemini');

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
assert.equal(requiredScopeForPath('/brain/unknown','GET'),null);

console.log('UNIVERSAL_AUTH_TESTS=PASS');
