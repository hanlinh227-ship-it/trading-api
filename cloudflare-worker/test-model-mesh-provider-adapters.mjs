import assert from 'node:assert/strict';
import {callCloudflareAI} from './model-mesh/providers/cloudflare-ai.js';
import {callGemini} from './model-mesh/providers/gemini.js';

const messages=[{role:'user',content:'Reply with OK only.'}];
let cloudflareUrl='';
const cloudflare=await callCloudflareAI({
  accountId:'account-id',apiKey:'cloudflare-secret',model:'@cf/zai-org/glm-4.7-flash',messages,
  fetchImpl:async(url,init)=>{
    cloudflareUrl=String(url);
    assert.equal(init.headers.Authorization,'Bearer cloudflare-secret');
    return new Response(JSON.stringify({result:{response:'OK'}}),{status:200,headers:{'content-type':'application/json'}});
  },
});
assert.equal(cloudflare.ok,true);
assert.equal(cloudflareUrl,'https://api.cloudflare.com/client/v4/accounts/account-id/ai/run/%40cf/zai-org/glm-4.7-flash');

let geminiUrl='';
const gemini=await callGemini({
  apiKey:'gemini-secret',model:'gemini-2.5-flash',messages,
  fetchImpl:async(url,init)=>{
    geminiUrl=String(url);
    assert.equal(init.headers['x-goog-api-key'],'gemini-secret');
    assert.equal(geminiUrl.includes('gemini-secret'),false);
    return new Response(JSON.stringify({candidates:[{content:{parts:[{text:'OK'}]}}]}),{status:200,headers:{'content-type':'application/json'}});
  },
});
assert.equal(gemini.ok,true);
assert.equal(geminiUrl,'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent');
console.log('model mesh provider adapter request contracts ok');
