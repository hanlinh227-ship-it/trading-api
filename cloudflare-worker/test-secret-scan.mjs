import assert from 'node:assert/strict';
import {assertNoCredentialLeak,collectSecretValues,findCredentialLeaks,redactCredentials} from './security/secret-scan.js';

// --- Regression for the production blocker -------------------------------
// GitHub Actions run 34980048523 step "Production TinyFish free evidence
// canary" exited 3 because the fetched page https://docs.tinyfish.ai/fetch-api
// contains the WORDS API_KEY / token / secret. That is documentation prose,
// not a credential leak, and must not fail the gate.
const benignDocs=JSON.stringify({ok:true,provider:'tinyfish',operation:'fetch',evidence:[{
  title:'Fetch API — TinyFish',
  url:'https://docs.tinyfish.ai/fetch-api',
  snippet:'Pass your API_KEY in the X-API-Key header. Keep the token secret. '+
          'Example: curl -H "X-API-Key: YOUR_API_KEY" https://api.fetch.tinyfish.ai '+
          'Never commit your secret token to source control. Authorization: Bearer <YOUR_TOKEN>',
}]});
assert.deepEqual(findCredentialLeaks(benignDocs),[],'benign documentation prose must not be flagged');
assert.deepEqual(assertNoCredentialLeak(benignDocs),{clean:true});

// The old vocabulary gate would have rejected this. Prove the difference.
assert.equal(/API_KEY|TOKEN|secret/i.test(benignDocs),true,'fixture must still contain the words the old gate matched');

// --- Real credentials must still be caught -------------------------------
for(const [label,leak] of [
  ['openai','{"text":"sk-proj-Ab12Cd34Ef56Gh78Ij90Kl12Mn34"}'],
  ['google','{"text":"AIzaSyD-aBcDeFgHiJkLmNoPqRsTuVwXyZ01234"}'],
  ['huggingface','{"text":"hf_QwErTyUiOpAsDfGhJkLzXcVbNm12"}'],
  ['groq','{"text":"gsk_QwErTyUiOpAsDfGhJkLzXcVbNm12"}'],
  ['bearer','{"h":"Authorization: Bearer ya29.A0ARrdaM9xQwErTyUiOpAsDfGhJkL"}'],
  ['jwt','{"t":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27u"}'],
  ['private_key','{"k":"-----BEGIN PRIVATE KEY-----"}'],
]){
  const found=findCredentialLeaks(leak);
  assert.ok(found.length>0,`${label} credential must be detected`);
  assert.throws(()=>assertNoCredentialLeak(leak),/credential_leak_detected/,`${label} must throw`);
  // The thrown message must name the shape, never the value.
  try{assertNoCredentialLeak(leak);}catch(error){
    assert.equal(error.message.includes(JSON.parse(leak)[Object.keys(JSON.parse(leak))[0]]),false,`${label} error must not echo the value`);
  }
}

// Documentation placeholders are not credentials.
assert.deepEqual(findCredentialLeaks('use sk-YOUR_API_KEY_HERE or Bearer <YOUR_TOKEN> or Bearer YOUR_API_KEY'),[]);
assert.deepEqual(findCredentialLeaks('AIzaSyEXAMPLEEXAMPLEEXAMPLEEXAMPLEEXAMPLE'),[]);

// --- Literal env values leak even without a known shape ------------------
const env={GROQ_API_KEY:'zzTotallyOpaqueValue123456',SHORT:'abc'};
const secretValues=collectSecretValues(env,['GROQ_API_KEY','SHORT','MISSING']);
assert.equal(secretValues.length,1,'short and missing values must not be matchable');
const leaked=findCredentialLeaks('response contains zzTotallyOpaqueValue123456 inline',{secretValues});
assert.deepEqual(leaked,[{kind:'env_value',detail:'GROQ_API_KEY'}]);
// Name is reported, value is not.
try{assertNoCredentialLeak('zzTotallyOpaqueValue123456',{secretValues});}
catch(error){
  assert.match(error.message,/env_value:GROQ_API_KEY/);
  assert.equal(error.message.includes('zzTotallyOpaqueValue123456'),false);
}
// A short binding must not make every string look like a leak.
assert.deepEqual(findCredentialLeaks('abc abc abc',{secretValues}),[]);

// --- Redaction preserves prose, removes credentials ----------------------
const redacted=redactCredentials('Keep the token secret. Key: sk-proj-Ab12Cd34Ef56Gh78Ij90Kl12Mn34',{secretValues});
assert.match(redacted,/Keep the token secret\./,'prose must survive redaction');
assert.equal(redacted.includes('sk-proj-Ab12Cd34Ef56Gh78Ij90Kl12Mn34'),false);
assert.match(redacted,/\[REDACTED\]/);
assert.equal(redactCredentials('zzTotallyOpaqueValue123456',{secretValues}),'[REDACTED]');

console.log('credential-shape leak detection ok');
