// Declared provider adapters. Adding a provider here is a policy change: it must state
// every field of the adapter contract, and anything it cannot state keeps it inactive.
export const AI_HORDE_ADAPTER=Object.freeze({
  id:'ai_horde',
  type:'community_volunteer_compute',
  baseUrl:'https://aihorde.net/api/v2',
  costMode:'FREE_ONLY',
  monetaryCost:'zero',
  paidFallback:false,
  autoPurchase:false,
  // Volunteer workers see every prompt, and anonymous requests are always shared, so this
  // provider is PUBLIC-only and never reference-safe.
  privacyClasses:Object.freeze(['PUBLIC']),
  referenceSafe:false,
  supportedTasks:Object.freeze(['TEXT_TO_IMAGE','MULTI_SCENE_BATCH']),
  supportedModels:Object.freeze(['stable_diffusion_xl']),
  maxResolution:Object.freeze({width:1536,height:1536}),
  healthEndpoint:'/status/heartbeat',
  queueBehavior:'async_poll',
  timeout:Object.freeze({submitMs:20000,pollMs:15000,cancelMs:15000}),
  retryPolicy:Object.freeze({maxAttempts:3,backoff:'exponential'}),
  rateLimitBehavior:'fail_closed',
  provenance:'https://github.com/Haidra-Org/AI-Horde',
  licenseEvidence:'AI Horde software is AGPL-3.0; per-model licenses are tracked in the model vault.',
});

const ADAPTERS=Object.freeze([AI_HORDE_ADAPTER]);

export function listProviderAdapters(){return ADAPTERS.map(adapter=>({...adapter}));}
export function getProviderAdapter(id){
  const match=ADAPTERS.find(adapter=>adapter.id===String(id||''));
  return match?{...match}:null;
}
