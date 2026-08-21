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
const required=[
  'index.js',
  'hub-v10.js',
  'signal-v10-council.js',
  'signal-v10-learning.js',
  'engine-v77168.js',
  'hub-v77171.js',
  'binance-control-plane.js',
  'adaptive-tuning.js',
  'ai-arbiter.js',
  'providers/entry-intelligence.js',
  'providers/decision-evidence.js',
  'providers/telegram-client.js'
];
for(const f of required)if(!fs.existsSync(path.join(root,f)))errors.push(`REQUIRED missing ${f}`);
const index=fs.readFileSync(path.join(root,'index.js'),'utf8');
if(!index.includes('hub-v10.js'))errors.push('SOURCE_OF_TRUTH index.js must import hub-v10.js');
if(!index.includes('const VERSION="V10"'))errors.push('SOURCE_OF_TRUTH index.js must expose VERSION V10');
if(errors.length){console.error(`Worker V10 preflight FAILED (${errors.length})`);for(const x of errors)console.error(`- ${x}`);process.exit(1);}
console.log(`Worker V10 preflight PASS: ${files.length} JS/MJS files, imports resolved, V10 source-of-truth locked.`);
