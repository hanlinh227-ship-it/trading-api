import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const registryPath=path.resolve(here,'../AI_SKILL_LIBRARY/v4/model_mesh/runtime_bindings.json');
assert.equal(fs.existsSync(registryPath),true,'runtime binding registry must exist');
const registry=JSON.parse(fs.readFileSync(registryPath,'utf8'));
assert.equal(registry.version,1);
const expected=['groq','gemini_developer_api','cloudflare_workers_ai','openrouter','mistral','cohere','huggingface_inference_providers','nvidia_nim','cerebras','sambanova','alibaba_model_studio','opencode_zen'];
for(const providerId of expected){
  const row=registry.bindings?.[providerId];
  assert.ok(row,`missing runtime binding: ${providerId}`);
  assert.equal(typeof row.endpoint_family,'string');
  assert.equal(typeof row.endpoint_url,'string');
  assert.equal(typeof row.secret_name,'string');
  assert.ok(/^[A-Z0-9_]+$/.test(row.secret_name),`unsafe secret env name: ${providerId}`);
  assert.equal('secret_value' in row,false);
  assert.equal(/(?:sk-|AIza|hf_)[A-Za-z0-9_-]{8,}/.test(JSON.stringify(row)),false,`credential-like value in binding: ${providerId}`);
}
console.log(`model mesh runtime bindings contract ok providers=${expected.length}`);
