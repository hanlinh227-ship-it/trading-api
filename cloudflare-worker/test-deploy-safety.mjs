import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {canonicalPreparationEnv} from './workers-build-contract.mjs';
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
assert.doesNotMatch(wranglerExample,/"crons"/);
assert.doesNotMatch(workflow,/echo\s+['"]?\$\{?TINY_FISH_API/);
assert.match(workflow,/cron: '\*\/10 \* \* \* \*'/);
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

console.log('deployment secret, rollback, authority and live-canary contracts ok');
