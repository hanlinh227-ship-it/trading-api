// Credential-shape leak detection.
//
// Rationale: matching the WORDS "API_KEY", "TOKEN" or "secret" flags ordinary
// documentation prose (an API docs page legitimately contains all three) while
// missing an actual credential that happens not to use those words. Detection
// must therefore key on credential SHAPE and on the concrete secret VALUES this
// runtime holds -- never on vocabulary.

// Known provider credential shapes. Each requires a provider-specific prefix
// plus enough entropy-bearing characters that prose cannot match by accident.
const CREDENTIAL_SHAPES=Object.freeze([
  {id:'openai_style',pattern:/\bsk-(?:proj-|ant-|or-v1-|live-)?[A-Za-z0-9_-]{16,}/},
  {id:'google_api_key',pattern:/\bAIza[0-9A-Za-z_-]{30,}/},
  {id:'huggingface',pattern:/\bhf_[A-Za-z0-9]{20,}/},
  {id:'groq',pattern:/\bgsk_[A-Za-z0-9]{20,}/},
  {id:'cerebras',pattern:/\bcsk-[A-Za-z0-9]{20,}/},
  {id:'xai',pattern:/\bxai-[A-Za-z0-9]{20,}/},
  {id:'github',pattern:/\bgh[pousr]_[A-Za-z0-9]{30,}/},
  {id:'aws_access_key',pattern:/\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/},
  {id:'slack',pattern:/\bxox[abposr]-[A-Za-z0-9-]{10,}/},
  {id:'jwt',pattern:/\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/},
  {id:'private_key_block',pattern:/-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----/,literal:true},
  // An Authorization header carrying a real bearer value. "Bearer <token>" or
  // "Bearer YOUR_API_KEY" in documentation is a placeholder, not a credential,
  // so placeholder-shaped values are excluded below.
  {id:'bearer_header',pattern:/\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*/},
]);

// Prefixes carried by the shapes above. Stripped before placeholder analysis so
// that `sk-YOUR_API_KEY_HERE` is judged on `YOUR_API_KEY_HERE`.
const SHAPE_PREFIX=/^(?:sk-(?:proj-|ant-|or-v1-|live-)?|AIza|hf_|gsk_|csk-|xai-|gh[pousr]_|xox[abposr]-)/;

// An uppercase run that documentation uses to mark a fill-in-the-blank value.
// Matched as an uppercase run so a real base64 credential containing the
// letters "test" in mixed case is NOT excused.
const PLACEHOLDER_WORD=/(?:YOUR|MY_|EXAMPLE|SAMPLE|PLACEHOLDER|REDACTED|DUMMY|FAKE|INSERT|ADD_|TODO|CHANGEME|XXXXX)/;

const MIN_ENV_VALUE_LENGTH=8;

/**
 * A documentation placeholder, not a credential.
 *
 * Trade-off, stated explicitly: this deliberately errs toward NOT flagging
 * fill-in-the-blank text, because this gate's job is catching *our own*
 * credentials escaping into output -- and those are caught literally by the
 * env-value check in findCredentialLeaks, which no placeholder rule can excuse.
 * Shape matching is the secondary net for third-party credentials.
 */
function isPlaceholder(match){
  const value=String(match).replace(/^Bearer\s+/i,'').trim().replace(SHAPE_PREFIX,'');
  if(!value)return true;
  // Bracketed/asterisked/elided forms: <token>, {{KEY}}, [key], xxxxx, ****
  if(/^(?:<[^>]*>|\{+[^}]*\}+|\[[^\]]*\]|x{3,}|\.{3,}|\*{3,})$/i.test(value))return true;
  // No lowercase at all -- real opaque credentials are mixed-case.
  if(!/[a-z]/.test(value))return true;
  // Contains an uppercase placeholder marker run.
  return PLACEHOLDER_WORD.test(value);
}

/**
 * Collect secret values worth matching literally. Only values long enough to be
 * a real credential are used, so a short or empty binding cannot make every
 * string look like a leak.
 */
export function collectSecretValues(env={},names=[]){
  const values=[];
  for(const name of names){
    const value=env?.[name];
    if(typeof value==='string'&&value.length>=MIN_ENV_VALUE_LENGTH)values.push({name,value});
  }
  return values;
}

/**
 * Scan text for credential leaks.
 * Returns the findings as {kind, detail} where `detail` NEVER contains the
 * matched value -- only the shape id or the env NAME that leaked.
 */
export function findCredentialLeaks(text,{secretValues=[]}={}){
  const haystack=String(text??'');
  const findings=[];
  for(const {name,value} of secretValues){
    if(value&&haystack.includes(value))findings.push({kind:'env_value',detail:name});
  }
  for(const {id,pattern,literal} of CREDENTIAL_SHAPES){
    const matches=haystack.match(new RegExp(pattern.source,'g'));
    if(!matches)continue;
    // A literal shape (an actual PEM header) is never a fill-in-the-blank.
    if(!literal&&matches.every(isPlaceholder))continue;
    findings.push({kind:'credential_shape',detail:id});
  }
  return findings;
}

export function assertNoCredentialLeak(text,options={}){
  const findings=findCredentialLeaks(text,options);
  if(findings.length)throw new Error(`credential_leak_detected:${findings.map(f=>`${f.kind}:${f.detail}`).sort().join(',')}`);
  return {clean:true};
}

/** Replace credential-shaped substrings with a marker, leaving prose intact. */
export function redactCredentials(text,{secretValues=[]}={}){
  let out=String(text??'');
  for(const {value} of secretValues){if(value)out=out.split(value).join('[REDACTED]');}
  for(const {pattern,literal} of CREDENTIAL_SHAPES){
    out=out.replace(new RegExp(pattern.source,'g'),match=>(!literal&&isPlaceholder(match))?match:(/^Bearer\s/i.test(match)?'Bearer [REDACTED]':'[REDACTED]'));
  }
  return out;
}

export const PROVIDER_SECRET_NAMES=Object.freeze(['MODEL_MESH_EXECUTION_TOKEN','TINY_FISH_API','GROQ_API_KEY','GEMINI_API_KEY','CLOUDFLARE_AI_API_TOKEN','OPENROUTER_API_KEY','MISTRAL_API_KEY','COHERE_API_KEY','HF_TOKEN','NVIDIA_API_KEY','CEREBRAS_API_KEY','SAMBANOVA_API_KEY','DASHSCOPE_API_KEY','OPENCODE_ZEN_API_KEY','CLOUDFLARE_API_TOKEN','TRADING_KV_NAMESPACE_ID','AI_BRIDGE_SERVICE_ID','V11_AI_BRIDGE_SERVICE_ID']);
