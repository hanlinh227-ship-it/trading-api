const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}

s=s.replaceAll('V77.11.0','V77.11.1');
s=s.replaceAll('Trading V77.11.1 Dynamic Regime Entry Hub','Trading V77.11.1 Dynamic Regime Entry Hub');

// Official 2026 ticker rename: Toncoin/TON -> Gram/GRAM. Keep 61-asset universe current.
mustReplace('"SUI","TAO","TIA","TON","TRUMP"','"SUI","TAO","TIA","GRAM","TRUMP"','crypto universe TON to GRAM');

// V73 was frozen before the ticker rename. Map only the historical prior key, never market data identity.
const oldEntry='function v73Entry(symbol,type){let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=norm(symbol).replace(/USDT$/,"");if(!key)return null;return V73_CONFIG?.[type]?.symbols?.[key]||null;}';
const newEntry='function v73CryptoPriorKey(symbol){const k=norm(symbol).replace(/USDT$/,"");return k==="GRAM"?"TON":k;}\nfunction v73Entry(symbol,type){let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=v73CryptoPriorKey(symbol);if(!key)return null;return V73_CONFIG?.[type]?.symbols?.[key]||null;}';
mustReplace(oldEntry,newEntry,'v73Entry prior rename map');

const oldPrior='const e=v73Entry(symbol,type);let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=norm(symbol).replace(/USDT$/,"");';
const newPrior='const e=v73Entry(symbol,type);let key=null;if(type==="forex")key=norm(symbol);if(type==="crypto")key=v73CryptoPriorKey(symbol);';
mustReplace(oldPrior,newPrior,'v73Prior key map');

// Accept legacy user input TON/TONUSDT, but canonicalize before any market-data request.
const runStart='async function runSymbol(symbol,env){\n  const s=norm(symbol),type=marketType(s);';
const runNew='function canonicalUserSymbol(symbol){const x=norm(symbol);if(x==="TON"||x==="TONUSDT")return "GRAMUSDT";return x;}\nasync function runSymbol(symbol,env){\n  const s=canonicalUserSymbol(symbol),type=marketType(s);';
mustReplace(runStart,runNew,'runSymbol legacy ticker canonicalization');

// Telegram /coin TON and /analyze TONUSDT should resolve to current GRAMUSDT.
mustReplace('let symbol=norm(cm[1]);if(CRYPTO_BASE.includes(symbol))symbol=symbol+"USDT";','let symbol=canonicalUserSymbol(cm[1]);if(symbol==="GRAMUSDT"){}else if(CRYPTO_BASE.includes(symbol))symbol=symbol+"USDT";','Telegram ticker canonicalization');

// Status should make the rename visible rather than silently hiding it.
mustReplace('Crypto: 61 symbol • exact 5TF + bid/ask','Crypto: 61 symbol • exact 5TF + bid/ask • TON→GRAM canonical','status ticker note');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.11.1 canonical TON to GRAM ticker migration');
