import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';

const root=process.cwd();
const files=fs.readdirSync(root).filter(f=>/\.(?:js|mjs)$/.test(f)).sort();
const errors=[];
for(const f of files){
  try{execFileSync(process.execPath,['--check',f],{cwd:root,stdio:'pipe'});}catch(e){errors.push(`SYNTAX ${f}: ${String(e?.stderr||e?.message||e).trim()}`);}
}
const importRe=/\b(?:import|export)\s+(?:[^'";]+?\s+from\s+)?["'](\.\.?\/[^"']+)["']/g;
for(const f of files){
  const src=fs.readFileSync(path.join(root,f),'utf8');
  for(const m of src.matchAll(importRe)){
    const spec=m[1];
    if(!spec.startsWith('.'))continue;
    const p=path.resolve(root,path.dirname(f),spec);
    if(!fs.existsSync(p))errors.push(`IMPORT ${f}: missing ${spec}`);
  }
}
const required=['index.js','engine-v77168.js','hub-v77171.js','hyro-runtime.js','hyro-scanner.js','hyro-execution.js','system-health.js','adaptive-tuning.js','ai-arbiter.js','dual-ai-intervention.js','claude-reviewer.js','claude-telegram.js'];
for(const f of required)if(!fs.existsSync(path.join(root,f)))errors.push(`REQUIRED missing ${f}`);
if(errors.length){console.error(`Worker preflight FAILED (${errors.length})`);for(const x of errors)console.error(`- ${x}`);process.exit(1);}
console.log(`Worker preflight PASS: ${files.length} JS/MJS files, imports resolved.`);
