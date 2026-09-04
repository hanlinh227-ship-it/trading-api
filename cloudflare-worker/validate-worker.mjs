import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';

const root=process.cwd(),errors=[];
const skip=new Set(['node_modules','.wrangler']);
function walk(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){if(skip.has(e.name))continue;const p=path.join(d,e.name);if(e.isDirectory())walk(p);else if(/\.(js|mjs)$/.test(e.name)){try{execFileSync(process.execPath,['--check',p],{cwd:root,stdio:'pipe'});}catch(x){errors.push(`SYNTAX ${path.relative(root,p)} ${String(x.stderr||x.message)}`);}}}}
walk(root);

const required=['index.js','bybit-runtime-contract.js','bybit-auto-config.js','bybit-auto-controller.js','bybit-auto-hub.js','bybit-control-plane.js','bybit-readonly-health.js','bybit-v5-client.js','bybit-btc-balance-reconciler.js','bybit-btc-microstructure-client.js','bybit-btc-market-state.js','bybit-btc-strategy.js','bybit-btc-risk-engine.js','bybit-btc-engine.js','providers/bybit-signed-client.js','providers/telegram-client.js'];
for(const f of required)if(!fs.existsSync(path.join(root,f)))errors.push(`MISSING ${f}`);

const forbiddenFiles=['bybit-auto-v1.js'];
for(const f of forbiddenFiles)if(fs.existsSync(path.join(root,f)))errors.push(`LEGACY BOT FILE MUST BE REMOVED ${f}`);

function reachableImports(entry){
  const seen=new Set(),stack=[entry];
  while(stack.length){const rel=stack.pop();if(seen.has(rel))continue;seen.add(rel);const abs=path.join(root,rel);if(!fs.existsSync(abs)){errors.push(`RUNTIME_IMPORT_MISSING ${rel}`);continue;}const txt=fs.readFileSync(abs,'utf8');const re=/(?:import|export)\s+(?:[^'";]*?\s+from\s+)?["'](\.\.?\/[^"']+)["']/g;let m;while((m=re.exec(txt))){let target=path.normalize(path.join(path.dirname(rel),m[1]));if(!path.extname(target))target+='.js';if(!fs.existsSync(path.join(root,target)))errors.push(`RUNTIME_IMPORT_MISSING ${rel} -> ${target}`);else stack.push(target);}}
  return seen;
}
const runtime=reachableImports('index.js');
const forbiddenPrefixes=['forex-','meme-','binance-','hyro-','hub-v10','hub-v11','hub-v77','signal-v10','multi-ai-control-plane','gpt-5ai-action','bybit-scalp-engine','bybit-adaptive-edge','bybit-ai-scalp-gate','bybit-learning-engine','bybit-evolution-engine'];
for(const f of runtime)for(const x of forbiddenPrefixes)if(path.basename(f).toLowerCase().startsWith(x.toLowerCase()))errors.push(`OLD_BOT_REACHABLE ${f}`);

if(errors.length){console.error(`BTC worker preflight FAILED (${errors.length})`);for(const e of errors)console.error('- '+e);process.exit(1);}
console.log(`BTC_WORKER_PREFLIGHT=PASS runtimeModules=${runtime.size}`);
