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
  authentication:'anonymous_optional_key',
  // Anonymous use has no account and no payment method, so the provider has no way to
  // charge us; exhausting capacity queues or fails rather than billing.
  freeAllocation:Object.freeze({unit:'volunteer_capacity',hardStop:true,overageBillingEnabled:false}),
});

// Cloudflare Workers AI. This is the same vendor already running the Worker and holding
// its KV and Durable Object state, so a reference image handled here does not reach a new
// third party: that is what makes it the reference-safe runtime, where AI Horde is not.
// On the Workers Free plan the daily Neuron allocation hard-stops, so it cannot bill.
export const CLOUDFLARE_WORKERS_AI_ADAPTER=Object.freeze({
  id:'cloudflare_workers_ai',
  type:'first_party_serverless_inference',
  baseUrl:'https://api.cloudflare.com/client/v4/accounts',
  costMode:'FREE_ONLY',
  monetaryCost:'zero',
  paidFallback:false,
  autoPurchase:false,
  privacyClasses:Object.freeze(['PUBLIC','INTERNAL','CONFIDENTIAL']),
  referenceSafe:true,
  supportedTasks:Object.freeze([
    'TEXT_TO_IMAGE','MULTI_SCENE_BATCH','REFERENCE_GENERATION','IMAGE_EDIT_GLOBAL',
    'IMAGE_EDIT_LOCAL','INPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','STYLE_TRANSFER','TARGETED_REPAIR',
  ]),
  // Model IDs verified against Cloudflare's published Workers AI model catalogue.
  supportedModels:Object.freeze([
    '@cf/black-forest-labs/flux-1-schnell',
    '@cf/stabilityai/stable-diffusion-xl-base-1.0',
    '@cf/runwayml/stable-diffusion-v1-5-img2img',
    '@cf/runwayml/stable-diffusion-v1-5-inpainting',
    '@cf/llava-hf/llava-1.5-7b-hf',
    '@cf/meta/llama-3.2-11b-vision-instruct',
  ]),
  maxResolution:Object.freeze({width:1024,height:1024}),
  healthEndpoint:'/ai/models/search',
  queueBehavior:'synchronous_binding',
  timeout:Object.freeze({submitMs:30000,pollMs:0,cancelMs:0}),
  retryPolicy:Object.freeze({maxAttempts:2,backoff:'linear'}),
  rateLimitBehavior:'fail_closed',
  provenance:'https://developers.cloudflare.com/workers-ai/models/',
  licenseEvidence:'Cloudflare licenses the served models; per-model licenses are tracked in the model vault and never redistributed by this repository.',
  authentication:'worker_ai_binding',
  // Workers Free plan: requests fail once the daily allocation is spent. Overage billing
  // only exists on the Workers Paid plan and is not enabled for this account.
  freeAllocation:Object.freeze({unit:'neurons',dailyNeurons:10000,hardStop:true,overageBillingEnabled:false,plan:'workers_free'}),
});

// Pollinations: no account, no API key and no payment method, so it has no mechanism to
// bill us. It is still a public third-party service, so it stays PUBLIC-only and is never
// handed a reference or source image.
export const POLLINATIONS_ADAPTER=Object.freeze({
  id:'pollinations',
  type:'public_community_service',
  baseUrl:'https://image.pollinations.ai',
  costMode:'FREE_ONLY',
  monetaryCost:'zero',
  paidFallback:false,
  autoPurchase:false,
  privacyClasses:Object.freeze(['PUBLIC']),
  referenceSafe:false,
  supportedTasks:Object.freeze(['TEXT_TO_IMAGE','MULTI_SCENE_BATCH']),
  supportedModels:Object.freeze(['flux','turbo']),
  maxResolution:Object.freeze({width:1024,height:1024}),
  healthEndpoint:'/',
  queueBehavior:'synchronous_http',
  timeout:Object.freeze({submitMs:60000,pollMs:0,cancelMs:0}),
  retryPolicy:Object.freeze({maxAttempts:2,backoff:'linear'}),
  rateLimitBehavior:'fail_closed',
  provenance:'https://github.com/pollinations/pollinations',
  licenseEvidence:'Pollinations platform is open source (MIT); served model licenses are tracked in the model vault.',
  authentication:'none',
  freeAllocation:Object.freeze({unit:'fair_use_requests',hardStop:true,overageBillingEnabled:false}),
});

const ADAPTERS=Object.freeze([AI_HORDE_ADAPTER,CLOUDFLARE_WORKERS_AI_ADAPTER,POLLINATIONS_ADAPTER]);

export function listProviderAdapters(){return ADAPTERS.map(adapter=>({...adapter}));}
export function getProviderAdapter(id){
  const match=ADAPTERS.find(adapter=>adapter.id===String(id||''));
  return match?{...match}:null;
}
