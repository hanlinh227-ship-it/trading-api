const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
const required=[
  'version: "V77.14.3"',
  'function planSignal(',
  'function refinedLimitPlan(',
  'function conditionalPlanFromRoute(',
  'deepNonCryptoCandidates: 5',
  'function actionableRank(',
  'future:emptyGroup()',
  'callback_data:"symbols"',
  'symmarket:',
  'FUTURES_KNOWLEDGE',
  'MASSIVE_API_KEY'
];
for(const x of required)if(!s.includes(x))throw new Error('Missing prerequisite: '+x);
s=s.replaceAll('V77.14.3','V77.15.1');
s=s.replace('Trading V77.15.1 Context-Parity Actionable Hub','Trading V77.15.1 Consolidated Actionable Multi-Market Hub');
// Keep Hub-wide Twelve Data usage within the Grow55 design: Forex 28 H1 + 3*4 deep = 40; Metal 2 H1 + 2*4 deep = 10.
s=s.replace('deepNonCryptoCandidates: 5','deepNonCryptoCandidates: 3');
s=s.replace('function tdPlannedCost(group){return group==="forex"?48:group==="metal"?10:0;}','function tdPlannedCost(group){return group==="forex"?40:group==="metal"?10:0;}');
if(!s.includes('unifiedTdHubBudgetMax: 50'))s=s.replace('actionablePlanMaxAtr: 1.15,','actionablePlanMaxAtr: 1.15,\n  unifiedTdHubBudgetMax: 50,');
fs.writeFileSync(path,s);
console.log('Promoted canonical Worker to V77.15.1 consolidated actionable hub');
