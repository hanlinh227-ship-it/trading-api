const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}
function replaceRange(start,end,repl,label){const a=s.indexOf(start);if(a<0)throw new Error('Missing start '+label);const b=s.indexOf(end,a+start.length);if(b<0)throw new Error('Missing end '+label);s=s.slice(0,a)+repl+s.slice(b);}

if(!s.includes('V77.11.0')&&!s.includes('V77.11.1'))throw new Error('Unexpected source version');
s=s.replaceAll('V77.11.0','V77.11.1');
s=s.replace('Trading V77.11.0 Dynamic Regime Entry Hub','Trading V77.11.1 Dynamic Regime Entry Hub');

if(s.includes('"SUI","TAO","TIA","TON","TRUMP"'))s=s.replace('"SUI","TAO","TIA","TON","TRUMP"','"SUI","TAO","TIA","GRAM","TRUMP"');
if(!s.includes('"GRAM"'))throw new Error('GRAM universe migration failed');

if(!s.includes('function v73CryptoPriorKey(')){
  const block=`function v73CryptoPriorKey(symbol){const k=norm(symbol).replace(/USDT$/,"");return k==="GRAM"?"TON":k;}\nfunction v73Entry(symbol,type){\n  let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=v73CryptoPriorKey(symbol);if(!key)return null;\n  return V73_CONFIG?.[type]?.symbols?.[key]||null;\n}\n`;
  replaceRange('function v73Entry(symbol,type){','function v73Prior(symbol,type){',block,'v73Entry block');
}

s=s.replace('if(type==="crypto")key=norm(symbol).replace(/USDT$/,"");','if(type==="crypto")key=v73CryptoPriorKey(symbol);');

if(!s.includes('function canonicalUserSymbol(')){
  const marker='async function runSymbol(symbol,env){';
  const repl='function canonicalUserSymbol(symbol){const x=norm(symbol);if(x==="TON"||x==="TONUSDT")return "GRAMUSDT";return x;}\n'+marker;
  mustReplace(marker,repl,'canonical user symbol insert');
}
s=s.replace('const s=norm(symbol),type=marketType(s);','const s=canonicalUserSymbol(symbol),type=marketType(s);');
s=s.replace('let symbol=norm(cm[1]);if(CRYPTO_BASE.includes(symbol))symbol=symbol+"USDT";','let symbol=canonicalUserSymbol(cm[1]);if(!symbol.endsWith("USDT")&&CRYPTO_BASE.includes(symbol))symbol=symbol+"USDT";');

if(!s.includes('TON→GRAM canonical')){
  s=s.replace('Crypto: 61 symbol • exact 5TF + bid/ask','Crypto: 61 symbol • exact 5TF + bid/ask • TON→GRAM canonical');
}

fs.writeFileSync(path,s,'utf8');
console.log('Applied robust V77.11.1 GRAM canonical migration');
