import path from 'node:path';
import {existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {canonicalPreparationEnv} from './workers-build-contract.mjs';

if(process.env.WORKERS_CI==='1'){
  const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'..');
  const sourceSha=String(process.env.WORKERS_CI_COMMIT_SHA||'').trim().toLowerCase();
  if(!/^[a-f0-9]{40}$/.test(sourceSha))throw new Error('Workers Builds exact commit SHA is missing or invalid');
  const head=spawnSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','ignore']});
  if(head.error||head.status!==0)throw new Error('Workers Builds could not resolve checked-out HEAD');
  const checkedOutSha=String(head.stdout||'').trim().toLowerCase();
  if(checkedOutSha!==sourceSha)throw new Error('Workers Builds checked-out HEAD does not match WORKERS_CI_COMMIT_SHA');
  const command=(executable,args,options={})=>{
    const result=spawnSync(executable,args,{cwd:options.cwd||root,env:options.env||process.env,encoding:'utf8',stdio:'inherit'});
    if(result.error)throw result.error;
    if(result.status!==0)throw new Error(`${path.basename(executable)} failed with exit code ${result.status}`);
  };
  let python='';
  for(const candidate of ['python3','python']){
    const probe=spawnSync(candidate,['--version'],{encoding:'utf8',stdio:'ignore'});
    if(!probe.error&&probe.status===0){python=candidate;break;}
  }
  if(!python)throw new Error('Python is required to compile exact-SHA Brain snapshots in Workers Builds');
  command(python,['-m','pip','install','--disable-pip-version-check','-r',path.join(root,'AI_SKILL_LIBRARY','requirements.txt')]);
  command(python,[path.join(root,'AI_SKILL_LIBRARY','v4','tools','ci_validate.py'),'--source-sha',sourceSha,'--skip-tests']);
  const exactEnv=canonicalPreparationEnv(process.env,root,sourceSha);
  for(const script of ['prepare-skill-gateway.mjs','prepare-model-mesh.mjs','prepare-wrangler.mjs'])command(process.execPath,[path.join(here,script)],{cwd:here,env:exactEnv});
  console.log(`WORKERS_BUILD_EXACT_SNAPSHOT=PASS source_sha=${sourceSha}`);
}else{
  const here=path.dirname(fileURLToPath(import.meta.url));
  const required=['model-mesh-snapshot.js','model-mesh-active-candidate-index.js','model-mesh-bindings.js','model-mesh-policy.js','free-only-policy.js','skill-gateway-snapshot.js'];
  const missing=required.filter(name=>!existsSync(path.join(here,'generated',name)));
  if(missing.length)throw new Error(`Generated contracts missing: ${missing.join(', ')}. Run: python3 ../AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha $(git rev-parse HEAD) --skip-tests && npm run prepare:skill-gateway && npm run prepare:model-mesh`);
}
