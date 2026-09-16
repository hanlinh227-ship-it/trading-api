import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {canonicalPreparationEnv} from './workers-build-contract.mjs';
import {HEALTH_REFRESH_CRON,assertHealthOnlyCrons} from './model-mesh/scheduled-health.js';
const workflow=fs.readFileSync('../.github/workflows/deploy-skill-mandatory-fast-gateway.yml','utf8');
const wranglerPrep=fs.readFileSync('prepare-wrangler.mjs','utf8');
const workersBuildPrep=fs.readFileSync('prepare-workers-build.mjs','utf8');
const probeValidator=fs.readFileSync('validate-model-mesh-probe.mjs','utf8');
const canaryPolicy=fs.readFileSync('model-mesh/canary-policy.js','utf8');
const packageJson=JSON.parse(fs.readFileSync('package.json','utf8'));
const wranglerExample=fs.readFileSync('wrangler.example.jsonc','utf8');
assert.match(workflow,/TINY_FISH_API:\s*\$\{\{ secrets\.TINY_FISH_API \}\}/);
assert.match(workflow,/redact-deploy-output\.mjs/);
assert.match(probeValidator,/MODEL_MESH_PROBE_MATRIX/);
assert.match(canaryPolicy,/LIVE_HEALTHY/);
assert.match(workflow,/validate-model-mesh-probe\.mjs --require-healthy/);
assert.match(workflow,/validate-model-mesh-overlay\.mjs/);
assert.doesNotMatch(workflow,/configured\.some\(r=>!r\.ok/);
assert.match(workflow,/npm ci --ignore-scripts/);
assert.match(workflow,/MODEL_MESH_POST_PROBE_PLAN=PASS/);
assert.match(workflow,/Final exact-SHA deployment gate/);
assert.match(workflow,/FINAL_EXACT_SHA_GATE=PASS/);
assert.match(wranglerPrep,/TINYFISH_CIRCUIT/);
assert.match(wranglerPrep,/new_sqlite_classes/);
assert.match(wranglerExample,/TINYFISH_CIRCUIT/);
// Crons are no longer banned outright: a read-only Model Mesh health-refresh
// cron is required, because GitHub Actions cron demonstrably cannot hold the
// 30-minute LIVE_TTL (one firing in 4.9h). The invariant is now semantic --
// financial, trading, deploy and autonomous crons stay forbidden, and the
// generator itself refuses anything but the single health cron.
{
  const exampleCrons=[...wranglerExample.matchAll(/"crons"\s*:\s*\[([^\]]*)\]/g)]
    .flatMap(m=>[...m[1].matchAll(/"([^"]+)"/g)].map(x=>x[1]));
  assert.deepEqual(exampleCrons,[HEALTH_REFRESH_CRON],'only the health cron may be configured');
  assert.doesNotThrow(()=>assertHealthOnlyCrons(exampleCrons));
  assert.throws(()=>assertHealthOnlyCrons([...exampleCrons,'*/5 * * * *']),/unexpected_cron/);
  // The generator must validate its own output, not just emit it.
  assert.match(wranglerPrep,/assertHealthOnlyCrons\(config\.triggers\.crons\)/);
  // The scheduled handler stays health-only.
  assert.match(fs.readFileSync('index.js','utf8'),/async scheduled\(/);
}
assert.doesNotMatch(workflow,/echo\s+['"]?\$\{?TINY_FISH_API/);
// The health-refresh schedule must use fixed-minute entries: GitHub sheds
// high-frequency '*/N' schedules under load and the '*/10' form never produced
// a single run in this repository. The cadence must also stay inside the
// model-mesh LIVE_TTL_MS (30 min) so healthy evidence cannot expire between
// refreshes, and the refresh must be dispatchable so it can be proven on demand.
const cronLine=workflow.match(/cron: '([^']+)'/);
assert.ok(cronLine,'health refresh cron missing');
const [minuteField,...restFields]=cronLine[1].split(' ');
assert.doesNotMatch(minuteField,/\*\//,'health refresh must not use a */N minute field');
assert.deepEqual(restFields,['*','*','*','*'],'health refresh must run every hour');
const minutes=minuteField.split(',').map(Number);
assert.ok(minutes.length>=2&&minutes.every(m=>Number.isInteger(m)&&m>=0&&m<60),'fixed minute list required');
const sorted=[...minutes].sort((a,b)=>a-b);
const gaps=sorted.map((m,i)=>i===0?m+60-sorted[sorted.length-1]:m-sorted[i-1]);
assert.ok(Math.max(...gaps)<=25,`refresh gap ${Math.max(...gaps)}min must stay inside LIVE_TTL_MS (30min) with margin`);
assert.match(workflow,/mode == 'refresh-health'/);
assert.match(workflow,/options:/);
assert.match(workflow,/refresh-model-mesh-health/);
assert.match(workflow,/git merge-base --is-ancestor "\$deployed" HEAD/);
assert.match(workflow,/fetch-depth: 0/);
assert.match(packageJson.scripts.check,/^node prepare-workers-build\.mjs &&/);
assert.match(workersBuildPrep,/WORKERS_CI_COMMIT_SHA/);
assert.match(workersBuildPrep,/checked-out HEAD does not match WORKERS_CI_COMMIT_SHA/);
assert.doesNotMatch(workersBuildPrep,/alreadyPrepared/);
assert.match(workersBuildPrep,/ci_validate\.py/);
assert.match(workersBuildPrep,/--skip-tests/);
assert.match(workersBuildPrep,/prepare-skill-gateway\.mjs/);
assert.match(workersBuildPrep,/prepare-model-mesh\.mjs/);
assert.match(workersBuildPrep,/prepare-wrangler\.mjs/);
const mismatch=spawnSync(process.execPath,['prepare-workers-build.mjs'],{cwd:process.cwd(),env:{...process.env,WORKERS_CI:'1',WORKERS_CI_COMMIT_SHA:'0'.repeat(40)},encoding:'utf8'});
assert.notEqual(mismatch.status,0);
assert.match(`${mismatch.stdout}${mismatch.stderr}`,/checked-out HEAD does not match WORKERS_CI_COMMIT_SHA/);
const canonicalRoot=path.resolve('canonical-root');
const injected=canonicalPreparationEnv({SKILL_GATEWAY_SNAPSHOT_PATH:'attacker-skill.json',MODEL_MESH_SNAPSHOT_PATH:'attacker-model.json',MODEL_MESH_BINDINGS_PATH:'attacker-bindings.json',MODEL_MESH_FREE_POLICY_PATH:'attacker-policy.json'},canonicalRoot,'f'.repeat(40));
assert.equal(injected.SKILL_GATEWAY_SNAPSHOT_PATH,path.join(canonicalRoot,'AI_SKILL_LIBRARY','v4','runtime','generated','skill-gateway-snapshot.json'));
assert.equal(injected.MODEL_MESH_SNAPSHOT_PATH,path.join(canonicalRoot,'AI_SKILL_LIBRARY','v4','runtime','generated','model-mesh-snapshot.json'));
assert.equal(injected.MODEL_MESH_BINDINGS_PATH,path.join(canonicalRoot,'AI_SKILL_LIBRARY','v4','model_mesh','runtime_bindings.json'));
assert.equal(injected.MODEL_MESH_FREE_POLICY_PATH,path.join(canonicalRoot,'AI_SKILL_LIBRARY','v4','model_mesh','free_only_policy.json'));
// --- C1: production must never be left half-gated --------------------------
// Previously: deploy -> canary fails -> final exact-SHA gate SKIPPED, leaving
// the new revision live and unverified (run 34980048523).
assert.match(workflow,/Capture currently-live revision for deterministic rollback/,'rollback target must be captured before production is mutated');
assert.match(workflow,/PREVIOUS_GOOD_SHA=/,'previous live revision must be recorded');
assert.match(workflow,/name: Roll back to previously live exact revision\n\s+if: failure\(\)/,'rollback must trigger on core-gate failure');
assert.match(workflow,/ROLLBACK=PASS revision=\$PREVIOUS_GOOD_SHA/,'rollback must verify the restored revision');
assert.match(workflow,/name: Final exact-SHA deployment gate\n\s+if: always\(\)/,'the exact-SHA gate must always render a verdict');
assert.match(workflow,/name: Deployment record\n\s+if: always\(\)/,'the deployment record must always state what is live');
assert.match(workflow,/FINAL_EXACT_SHA_GATE=ROLLED_BACK/,'a rolled-back deploy must be reported distinctly, not as a pass');
assert.match(workflow,/PRODUCTION_LIVE_REVISION=/,'the record must report the revision actually serving traffic');
// The rollback rebuilds from the exact SHA, so full history is required.
assert.match(workflow,/ref: main\n\s+fetch-depth: 0/,'rollback needs full history to rebuild an earlier exact SHA');

// --- Phase 3: TinyFish is optional and must not gate the Brain deploy -------
assert.match(workflow,/Production TinyFish free evidence canary \(advisory, optional\)\n\s+id: tinyfish_canary\n\s+continue-on-error: true/,'TinyFish must not gate the mesh deployment');
assert.match(workflow,/validate-evidence-canary\.mjs --operation=search/);
assert.match(workflow,/validate-evidence-canary\.mjs --operation=fetch --require-evidence/);
// The vocabulary gate that blocked every deploy must not come back.
assert.doesNotMatch(workflow,/match\(\/API_KEY\|TOKEN\|secret\/i\)/,'leak detection must be credential-shaped, never vocabulary-based');
assert.match(workflow,/x\.optional!==true\|\|x\.hardDependency!==false/,'TinyFish health must advertise the optional contract');

// --- Security: least-privilege credential sync ------------------------------
assert.match(workflow,/MODEL_MESH_SECRETS_REQUIRED=/,'only providers with an eligible model may receive a credential');
assert.match(workflow,/MODEL_MESH_SECRETS_SKIPPED_NO_ELIGIBLE_MODEL=/);
assert.match(workflow,/PROVIDER_SECRET_SYNC=ELIGIBLE_PROVIDERS_ONLY/);

// --- M1: parallelism is echoed from the compiled contract, never re-typed ---
assert.doesNotMatch(workflow,/MODEL_MESH_MAX_PARALLEL_STANDARD=2/,'limits must come from the compiled canonical policy');
assert.match(workflow,/model-mesh-policy\.json/,'the record must read the compiled policy contract');

// --- H2: provider model availability is diagnosed from evidence -------------
assert.match(workflow,/GEMINI_MODEL_AVAILABILITY=/,'a 404 provider must be diagnosed against the live model listing');
assert.match(workflow,/Provider model availability diagnosis \(advisory\)\n\s+if: always\(\)\n\s+continue-on-error: true/);

const policyCompiler=fs.readFileSync('../AI_SKILL_LIBRARY/v4/tools/compile_model_mesh_policy.py','utf8');
assert.match(policyCompiler,/max_parallel\.FAST must be 0/,'FAST may never fan out to external workers');
assert.match(fs.readFileSync('prepare-model-mesh.mjs','utf8'),/endpoint_family conflict/,'endpoint_family must have a single owner');

// --- Single deployment authority ------------------------------------------
// Two workflows deployed the same Worker on the same trigger. On aa30bccf the
// gated workflow failed before its Model Mesh canaries ran while the other one
// deployed the revision anyway, so unverified code went live and the exact-SHA
// gate had nothing left to stop.
const otherDeploy=fs.readFileSync('../.github/workflows/deploy-cloudflare-worker.yml','utf8');
const realDeploy=/npx wrangler deploy(?!\s+--dry-run)/;
assert.doesNotMatch(otherDeploy,realDeploy,'only the gated workflow may deploy trading-v77-scanner');
assert.match(otherDeploy,/CLOUDFLARE_DEPLOY_AUTHORITY=deploy-skill-mandatory-fast-gateway\.yml/);
assert.match(otherDeploy,/CLOUDFLARE_WORKER_DEPLOY=DRY_RUN_ONLY/);
// The gate itself must still be the one that deploys, and that must survive.
assert.match(workflow,realDeploy,'the gated workflow must still perform the real deploy');

// --- FAST/SECRET boundaries proven against the running Worker --------------
assert.match(workflow,/SECRET_EXTERNAL_BOUNDARY=PASS/,'SECRET must be proven closed on production, not only in unit tests');
assert.match(workflow,/DATACLASS_FAIL_CLOSED=PASS/,'an unknown data class must fail closed to SECRET on production');
assert.match(workflow,/FAST_EXTERNAL_BOUNDARY=PASS/,'FAST must be proven to select zero external workers on production');

// --- Final hardening: canary text integrity ---------------------------------
// Three canary literals were mojibake ('sá»­a lá»—i API nÃ y'); they routed to a different
// primary skill and only passed because verify_live_plan never asserted the skill.
assert.doesNotMatch(workflow,/Ã|Â|á»/,'workflow canary strings must be valid UTF-8, not mojibake');
assert.match(workflow,/verify_live_plan 'sửa lỗi API này' debugging STANDARD 2/);
assert.match(workflow,/verify_live_plan 'quét market BTC live' trading_router DEEP 4/);
assert.match(workflow,/r\.primarySkill!==process\.env\.EXPECTED_SKILL/,'post-probe plan must assert the primary skill, not only the profile');

// --- Final hardening: deploy lock cannot be evicted by the health cron ------
// GitHub keeps one running + one pending run per concurrency group and cancels the
// older pending run. With the 20-minute refresh cron in the same group as the deploy,
// a queued production deploy could be cancelled by a health refresh and main would
// silently never deploy.
{
  const yamlText=workflow;
  assert.doesNotMatch(yamlText,/^concurrency:/m,'concurrency must be per job, not per workflow');
  assert.match(yamlText,/deploy-exact-main:[\s\S]*?concurrency:\n\s+group: cloudflare-zero-local-runtime-production\n\s+cancel-in-progress: false/);
  assert.match(yamlText,/refresh-model-mesh-health:[\s\S]*?concurrency:\n\s+group: cloudflare-model-mesh-health-refresh\n\s+cancel-in-progress: false/);
}

// --- Final hardening: ordering and gate shape --------------------------------
const idx=name=>{const i=workflow.indexOf(name);assert.ok(i>=0,`missing step: ${name}`);return i;};
assert.ok(idx('Capture currently-live revision for deterministic rollback')<idx('name: Deploy exact-main Worker'),'rollback target must be captured before the deploy');
assert.ok(idx('Capture currently-live revision for deterministic rollback')<idx('Sync configured Model Mesh secrets'),'secrets (a production mutation) are synced only after the rollback target is captured');
assert.ok(idx('Sync Universal Brain credentials')<idx('name: Deploy exact-main Worker'));
// The manual probe must run before any step that calls /brain/mesh/plan on the fresh
// revision: with zero live evidence, plan schedules a background self-heal probe that
// races the canary's probe writes (run 35072895068 failed closed on that race).
assert.ok(idx('name: Production Model Mesh provider canary')<idx('name: Production Model Mesh planner smoke'),'provider canary must precede the planner smoke');
assert.ok(idx('name: Production Model Mesh provider canary')<idx('name: Production FAST and SECRET external boundary proof'));
assert.equal((workflow.match(/npx wrangler deploy 2>&1 \| node redact-deploy-output\.mjs/g)||[]).length,2,'both real deploys (forward and rollback) must be piped through redaction');
assert.match(workflow,/x\.keep_vars!==true/,'generated config must keep dashboard vars');
assert.match(wranglerPrep,/keep_vars:true/);
assert.match(workflow,/runtime_switch_must_not_be_generated/);
assert.match(workflow,/provider_secret_must_not_be_generated/);
assert.match(workflow,/^permissions:\n\s+contents: read$/m);
assert.match(workflow,/test "\$SOURCE_SHA" = "\$GITHUB_SHA"/,'the locked SHA must be the SHA that triggered the run');
assert.doesNotMatch(workflow,/FAST_EXTERNAL_BOUNDARY=SKIPPED/,'the FAST boundary proof must not pass vacuously');
assert.match(workflow,/FINAL_EXACT_SHA_GATE=UNVERIFIED/,'a core-gate failure with no rollback target must not read as PASS');
assert.match(workflow,/CORE_GATE_FAILED=1/);
{
  const probeTimeouts=[...workflow.matchAll(/--max-time (\d+) -X POST -H "x-model-mesh-token: \$MODEL_MESH_EXECUTION_TOKEN" "\$WORKER_BASE_URL\/brain\/mesh\/probe"/g)].map(m=>Number(m[1]));
  assert.ok(probeTimeouts.length>=2,'probe curls present');
  for(const t of probeTimeouts)assert.ok(t>=180,`probe --max-time ${t}s must cover 2 batches x 3 candidates x 30s`);
}
{
  // Every provider secret visible to the job is exported on the real deploy step so
  // value-based redaction covers it.
  const deployStep=workflow.slice(idx('name: Deploy exact-main Worker'),idx('Verify exact deployed revision'));
  for(const key of ['GROQ_API_KEY','GEMINI_API_KEY','CLOUDFLARE_AI_API_TOKEN','OPENROUTER_API_KEY','MISTRAL_API_KEY','COHERE_API_KEY','HF_TOKEN','NVIDIA_API_KEY','CEREBRAS_API_KEY','SAMBANOVA_API_KEY','DASHSCOPE_API_KEY','OPENCODE_ZEN_API_KEY','MODEL_MESH_EXECUTION_TOKEN','TINY_FISH_API'])assert.match(deployStep,new RegExp(`${key}: \\$\\{\\{ secrets\\.${key} \\}\\}`),`${key} must be in scope of the deploy step for redaction`);
}

// --- Final hardening: npm run check must reach every test file ---------------
{
  const listed=new Set([...JSON.stringify(packageJson.scripts).matchAll(/node (test-[\w-]+\.mjs)/g)].map(m=>m[1]));
  for(const file of fs.readdirSync('.').filter(f=>/^test-.*\.mjs$/.test(f)))assert.ok(listed.has(file),`${file} is not reachable from npm run check`);
  assert.match(packageJson.scripts.check,/npm run test:universal-fabric/);
}

// --- Final hardening: no other workflow may really deploy trading-v77-scanner --
for(const file of fs.readdirSync('../.github/workflows').filter(f=>/\.ya?ml$/.test(f))){
  if(file==='deploy-skill-mandatory-fast-gateway.yml')continue;
  const text=fs.readFileSync(path.join('../.github/workflows',file),'utf8');
  if(realDeploy.test(text))assert.doesNotMatch(text,/trading-v77-scanner/,`${file} performs a real wrangler deploy and must not target trading-v77-scanner`);
}

console.log('deployment secret, rollback, authority, boundary and live-canary contracts ok');
