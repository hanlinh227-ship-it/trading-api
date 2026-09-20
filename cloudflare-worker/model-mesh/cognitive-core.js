export const COGNITIVE_CORE_ID='brain-cognition-v1';

export const COGNITIVE_CORE_TEXT=[
  'Follow the canonical Brain contract.',
  'Separate verified facts from inference.',
  'Current authority outranks cached or learned state.',
  'Measured capability outranks declared capability.',
  'Do not invent missing evidence or resolve material conflict by majority vote.',
  'Preserve provenance, use least permission, and verify material actions.',
  'Memory is context, not authority.',
  'Do not expose or persist hidden chain-of-thought, secrets, or credentials.'
].join(' ');

function verifiedCapabilities(worker){
  const evidence=worker?.capability_evidence&&typeof worker.capability_evidence==='object'?worker.capability_evidence:{};
  return Object.entries(evidence)
    .filter(([,row])=>row?.state==='VERIFIED')
    .map(([cap])=>cap)
    .sort()
    .slice(0,6);
}

export function buildCognitiveMessages(worker,route,text){
  const verified=verifiedCapabilities(worker);
  const role=String(worker?.worker_role||'maker');
  const domain=String(route?.domain||'core');
  const family=String(worker?.model_family||worker?.model_id||'unknown');
  const delta=[
    `Model family: ${family}.`,
    `Role: ${role}; domain: ${domain}.`,
    verified.length?`Measured capabilities: ${verified.join(', ')}.`:'No measured capability is attached to this worker for this task.',
    'Treat absent capabilities as unverified; use evidence and verifier feedback rather than confidence.'
  ].join(' ');
  return [
    {role:'system',content:COGNITIVE_CORE_TEXT},
    {role:'system',content:delta},
    {role:'user',content:String(text??'')},
  ];
}

export const _test={verifiedCapabilities};
