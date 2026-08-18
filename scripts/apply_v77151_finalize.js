const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
const required=[
  'version: "V77.14.3"',
  'function planSignal(',
  'function refinedLimitPlan(',
  'function conditionalPlanFromRoute(',
  'deepNonCryptoCandidates: 5',
  'future:emptyGroup()',
  'callback_data:"symbols"',
  'symmarket:',
  'FUTURES_KNOWLEDGE',
  'MASSIVE_API_KEY'
];
for(const x of required)if(!s.includes(x))throw new Error('Missing prerequisite: '+x);
s=s.replaceAll('V77.14.3','V77.15.1');
s=s.replace('Trading V77.15.1 Context-Parity Actionable Hub','Trading V77.15.1 Actionable Multi-Market Entry Hub');
fs.writeFileSync(path,s);
console.log('Promoted canonical Worker to V77.15.1');
