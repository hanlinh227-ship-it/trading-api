import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

if(process.env.WORKERS_CI==='1'){
  const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'..');
  const sourceSha=String(process.env.WORKERS_CI_COMMIT_SHA||'').trim().toLowerCase();
  if(!/^[a-f0-9]{40}$/.test(sourceSha))throw new Error('Workers Builds exact commit SHA is missing or invalid');

  const readSourceSha=file=>{try{return String(JSON.parse(fs.readFileSync(file,'utf8'))?.source_sha||'');}catch{return '';}};
  const skillSnapshot=path.join(root,'AI_SKILL_LIBRARY','v4','runtime','generated','skill-gateway-snapshot.json');
  const modelSnapshot=path.join(root,'AI_SKILL_LIBRARY','v4','runtime','generated','model-mesh-snapshot.json');
  const generated=[
    path.join(here,'generated','skill-gateway-snapshot.js'),
    path.join(here,'generated','model-mesh-snapshot.js'),
    path.join(here,'generated','model-mesh-bindings.js'),
    path.join(here,'generated','free-only-policy.js'),
    path.join(here,'wrangler.jsonc'),
  ];
  const alreadyPrepared=readSourceSha(skillSnapshot)===sourceSha&&readSourceSha(modelSnapshot)===sourceSha&&generated.every(file=>fs.existsSync(file));
  if(alreadyPrepared){
    console.log(`WORKERS_BUILD_EXACT_SNAPSHOT=READY source_sha=${sourceSha}`);
  }else{
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
    const exactEnv={...process.env,GITHUB_SHA:sourceSha,RUNTIME_REVISION:sourceSha};
    for(const script of ['prepare-skill-gateway.mjs','prepare-model-mesh.mjs','prepare-wrangler.mjs'])command(process.execPath,[path.join(here,script)],{cwd:here,env:exactEnv});
    console.log(`WORKERS_BUILD_EXACT_SNAPSHOT=PASS source_sha=${sourceSha}`);
  }
}
