// V78-010 — shared Bybit HMAC primitive.
// Extracted byte-for-byte from cloudflare-worker/hyro-execution.js,
// hyro-position-manager.js, hyro-position-review.js and hyro-demo-test.js.
// Scope is intentionally limited to hmacHex only; signedBybit/signed/
// publicBybit/publicJson/pub have real behavioral differences (error shape,
// mode-aware vs DEMO-only credentials, GET-vs-POST support) and are
// deliberately deferred to V78-010b.

const enc=new TextEncoder();
export async function hmacHex(secret,text){const key=await crypto.subtle.importKey("raw",enc.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);const sig=await crypto.subtle.sign("HMAC",key,enc.encode(text));return [...new Uint8Array(sig)].map(b=>b.toString(16).padStart(2,"0")).join("");}
