// Validates a /brain/evidence/* canary envelope from stdin.
//
// Replaces the previous inline gate `if(JSON.stringify(x).match(/API_KEY|TOKEN|secret/i))`
// which flagged ordinary API documentation prose and blocked every deploy
// (production run 34980048523). Leak detection is now credential-shaped and
// value-based; see security/secret-scan.js.
import {assertNoCredentialLeak,collectSecretValues,PROVIDER_SECRET_NAMES} from './security/secret-scan.js';

let input='';
for await(const chunk of process.stdin)input+=chunk;

const expectedOperation=(process.argv.find(arg=>arg.startsWith('--operation='))||'').split('=')[1]||'';
const requireEvidence=process.argv.includes('--require-evidence');

let envelope;
try{envelope=JSON.parse(input);}catch{console.error('EVIDENCE_CANARY=FAIL reason=invalid_json');process.exit(2);}

const secretValues=collectSecretValues(process.env,PROVIDER_SECRET_NAMES);
try{assertNoCredentialLeak(input,{secretValues});}
catch(error){console.error(`EVIDENCE_CANARY=FAIL reason=${error.message}`);process.exit(3);}

const problems=[];
if(envelope.ok!==true)problems.push(`ok=${envelope.ok} category=${envelope.category??'null'} status=${envelope.status??'null'}`);
if(envelope.provider!=='tinyfish')problems.push(`provider=${envelope.provider}`);
if(envelope.mode!=='FREE_ONLY')problems.push(`mode=${envelope.mode}`);
if(envelope.routingAuthority!==false)problems.push('routingAuthority must be false');
if(envelope.reasoningAuthority!==false)problems.push('reasoningAuthority must be false');
if(expectedOperation&&envelope.operation!==expectedOperation)problems.push(`operation=${envelope.operation} expected=${expectedOperation}`);
if(requireEvidence&&(!Array.isArray(envelope.evidence)||envelope.evidence.length===0))problems.push('evidence array empty');

if(problems.length){console.error(`EVIDENCE_CANARY=FAIL reason=${problems.join('; ')}`);process.exit(2);}
console.log(`EVIDENCE_CANARY=PASS operation=${envelope.operation} status=${envelope.status} evidence=${Array.isArray(envelope.evidence)?envelope.evidence.length:0} guardPersisted=${envelope.guardStatePersisted??'n/a'}`);
