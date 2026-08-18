const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}
if(!s.includes('V77.11.1'))throw new Error('Expected V77.11.1 source');
s=s.replaceAll('V77.11.1','V77.11.2');
s=s.replace('async function runSymbol(symbol,env){\n  const s=norm(symbol),type=marketType(s);','async function runSymbol(symbol,env){\n  const s=canonicalUserSymbol(symbol),type=marketType(s);');
if(!s.includes('async function runSymbol(symbol,env){\n  const s=canonicalUserSymbol(symbol),type=marketType(s);'))throw new Error('runSymbol canonicalization failed');
fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.11.2 identity consistency');
