# Universal Brain Adapter SDK

This package is the client-side bridge to the canonical `GITHUB_BRAIN_V4` Universal Brain Fabric.

## Runtime behavior

- Safe, provable `FAST` requests may route locally from a verified exact-SHA HOT snapshot with **zero network calls**.
- `STANDARD`, `DEEP`, live, trading, deployment/runtime, credential-sensitive, financial, destructive, and permission-changing requests go to the cloud Brain.
- If the cloud Brain is unavailable, only a safe non-high-impact request may use an explicitly supplied verified Stable snapshot. Protected requests fail closed.
- Candidate memory submission never activates memory. Promotion is handled by the Evergreen review principal and canonical memory gates.
- Tokens are supplied at runtime only. They are not stored in manifests, OpenAPI, logs, or repository configuration.

## Platform boundary

The repository and Worker endpoint **cannot force third-party consumer applications such as ChatGPT, Claude, or Gemini to intercept every chat automatically**. Each platform must provide a supported connector, custom action, plugin, MCP/tool hook, system integration, or another approved adapter mechanism, and that adapter must be installed/connected once on that platform.

After that connection exists, all supported clients use the same Brain endpoint and contract. Adding a future client does not require a new Brain core: register the adapter, provision a scoped credential, and use this SDK/HTTP contract.

Do not claim account-wide or product-wide automatic invocation until the target platform itself exposes and enables such a hook.

## Public manifests

`adapters/chatgpt.json`, `adapters/claude.json`, and `adapters/gemini.json` contain public endpoint metadata only. `openapi.yaml` documents the HTTP surface without credential values.

## SDK

```js
import {createBrainAdapter} from './index.mjs';

const adapter=createBrainAdapter({
  clientId:'chatgpt',
  token:process.env.BRAIN_CLIENT_CHATGPT_TOKEN,
  endpoint:process.env.BRAIN_ENDPOINT,
  hotSnapshot,
  stableSnapshot,
});

const route=await adapter.route({
  text:'explain recursion',
  request_id:'request-1',
  session_id:'session-1',
  data_class:'PUBLIC',
});
```

Run `npm test` to verify FAST zero-RTT, cloud routing, degraded fallback, and protected fail-closed behavior.
