import {validateModelVaultEntry} from './model-vault.js';
import {validateProviderAdapter} from './provider-adapter.js';
import {requiresReferenceSafeRuntime} from './provider-mesh.js';

const PRIVACY_SOURCES=Object.freeze({
  cloudflare_workers_ai:'https://developers.cloudflare.com/workers-ai/platform/data-usage/',
  ai_horde:'https://github.com/Haidra-Org/AI-Horde',
  pollinations:'https://github.com/pollinations/pollinations',
});

const LICENSE_SOURCES=Object.freeze({
  'flux-1-schnell':'https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/',
  'stable-diffusion-v1-5-img2img':'https://developers.cloudflare.com/workers-ai/models/stable-diffusion-v1-5-img2img/',
  'stable-diffusion-v1-5-inpainting':'https://developers.cloudflare.com/workers-ai/models/stable-diffusion-v1-5-inpainting/',
  'llama-3.2-11b-vision-instruct':'https://developers.cloudflare.com/workers-ai/models/llama-3.2-11b-vision-instruct/',
});

export function buildStaticActivationEvidence({model={},adapter={},taskType,at}={}){
  const verifiedAt=String(at||model.lastVerifiedAt||new Date().toISOString());
  const modelValidation=validateModelVaultEntry(model);
  const adapterValidation=validateProviderAdapter(adapter);
  const licenseSource=String(model.licenseEvidenceUrl||LICENSE_SOURCES[model.modelId]||'').trim();
  const privacySource=String(adapter.privacyEvidenceUrl||PRIVACY_SOURCES[adapter.id]||'').trim();

  const licenseOk=modelValidation.ok
    &&Boolean(String(model.licenseEvidence||'').trim())
    &&Boolean(licenseSource);

  const needsReferenceSafe=requiresReferenceSafeRuntime({taskType});
  const privacyClassOk=Array.isArray(adapter.privacyClasses)
    &&adapter.privacyClasses.includes('PUBLIC')
    &&(!needsReferenceSafe||adapter.referenceSafe===true);
  const privacyOk=adapterValidation.ok&&privacyClassOk&&Boolean(privacySource);

  return {
    license:{
      ok:licenseOk,
      at:verifiedAt,
      source:licenseSource||null,
      detail:licenseOk?`${model.codeLicense}/${model.weightsLicense}`:'license_evidence_incomplete',
    },
    privacy:{
      ok:privacyOk,
      at:verifiedAt,
      source:privacySource||null,
      detail:privacyOk
        ?(needsReferenceSafe?'reference_safe_provider_policy_verified':'public_data_policy_verified')
        :'privacy_evidence_incomplete',
    },
  };
}
