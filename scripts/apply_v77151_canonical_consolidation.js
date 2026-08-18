const fs=require('fs');
const p='cloudflare-worker/index.js';let s=fs.readFileSync(p,'utf8');
function must(a,b,l){if(!s.includes(a))throw new Error('Missing '+l);s=s.replace(a,b);}
if(s.includes('version: "V77.14.3"'))s=s.replace('version: "V77.14.3"','version: "V77.15.1"');else if(s.includes('version: "V77.15.0"'))s=s.replace('version: "V77.15.0"','version: "V77.15.1"');else throw new Error('Unexpected source version');
s=s.replace(/service: "Trading [^"]+"/,'service: "Trading V77.15.1 Consolidated Actionable Multi-Market Hub"');
must('deepNonCryptoCandidates: 5,','deepNonCryptoCandidates: 3,','unified TD quota deep count');
must('function tdPlannedCost(group){return group==="forex"?48:group==="metal"?10:0;}','function tdPlannedCost(group){return group==="forex"?40:group==="metal"?10:0;}','unified TD quota cost');
// Explicitly expose the invariant so future migrations cannot silently consume the Metal quota.
must('actionablePlanMaxAtr: 1.15,','actionablePlanMaxAtr: 1.15,\n  unifiedTdHubBudgetMax: 50,','unified budget marker');
// Plan statuses are advisory only; only MARKET/LIMIT enter durable books.
must('function fillBooks(group,books,analyses){const b=books[group],newItems=[];','function fillBooks(group,books,analyses){const b=books[group],newItems=[];','durable book marker');
fs.writeFileSync(p,s);console.log('Applied V77.15.1 canonical consolidation');
