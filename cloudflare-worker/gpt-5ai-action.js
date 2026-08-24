const PROVIDERS = [
  "claude",
  "codex",
  "deepseek",
  "qwen",
  "openrouter"
];

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff"
    }
  });

async function callBridge(env, payload) {
  if (!env.AI_BRIDGE || typeof env.AI_BRIDGE.fetch !== "function") {
    return {
      response: null,
      error: "AI_BRIDGE_BINDING_MISSING"
    };
  }

  const bridgeSecret = String(env.V11_AI_BRIDGE_SECRET || "");

  if (!bridgeSecret) {
    return {
      response: null,
      error: "AI_BRIDGE_SECRET_MISSING"
    };
  }

  try {
    const response = await env.AI_BRIDGE.fetch(
      new Request("http://127.0.0.1:8789/review", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "accept": "application/json",
          "authorization": "Bearer " + bridgeSecret
        },
        body: JSON.stringify({
          evidence: {
            mode: "GENERAL_5AI_COUNCIL",
            task_id: payload.task_id,
            instruction: payload.task,
            context: {
              mode: payload.mode,
              source: "CHATGPT_CUSTOM_ACTION"
            },
            requestedProviders: PROVIDERS
          }
        }),
        signal: AbortSignal.timeout(125000)
      })
    );

    return { response, error: null };
  } catch (error) {
    return {
      response: null,
      error:
        "AI_BRIDGE_FETCH_FAILED:" +
        String(error?.message || error)
    };
  }
}

export async function handleGpt5AiAction(req, env) {
  const url = new URL(req.url);

  if (url.pathname !== "/api/5ai/council") {
    return null;
  }

  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "POST, OPTIONS",
        "access-control-allow-headers":
          "Authorization, Content-Type"
      }
    });
  }

  if (req.method !== "POST") {
    return json(
      {
        ok: false,
        error: "METHOD_NOT_ALLOWED"
      },
      405
    );
  }

  const expectedKey = String(env.GPT_5AI_ACTION_KEY || "");

  if (!expectedKey) {
    return json(
      {
        ok: false,
        error: "GPT_5AI_ACTION_KEY_NOT_CONFIGURED"
      },
      503
    );
  }

  const authorization = String(
    req.headers.get("authorization") || ""
  );

  if (authorization !== "Bearer " + expectedKey) {
    return json(
      {
        ok: false,
        error: "UNAUTHORIZED"
      },
      401
    );
  }

  let body;

  try {
    body = await req.json();
  } catch {
    return json(
      {
        ok: false,
        error: "INVALID_JSON"
      },
      400
    );
  }

  const task = String(body?.task || "").trim();

  const mode = String(
    body?.mode || "general"
  ).trim();

  if (!task) {
    return json(
      {
        ok: false,
        error: "TASK_REQUIRED"
      },
      400
    );
  }

  if (task.length > 20000) {
    return json(
      {
        ok: false,
        error: "TASK_TOO_LARGE"
      },
      413
    );
  }

  const taskId =
    "gpt-5ai-" +
    Date.now() +
    "-" +
    crypto.randomUUID().slice(0, 8);

  const bridge = await callBridge(env, {
    task_id: taskId,
    task,
    mode
  });

  if (!bridge.response) {
    return json(
      {
        ok: false,
        task_id: taskId,
        error: bridge.error,
        providers: {}
      },
      503
    );
  }

  let result;

  try {
    result = await bridge.response.json();
  } catch {
    return json(
      {
        ok: false,
        task_id: taskId,
        error: "AI_BRIDGE_INVALID_JSON",
        providers: {}
      },
      502
    );
  }

  const providers = {};

  for (const provider of PROVIDERS) {
    providers[provider] =
      result?.providers?.[provider] || {
        status: "MISSING"
      };
  }

  const allFiveOk = PROVIDERS.every(
    provider =>
      String(
        providers[provider]?.status || ""
      ).toUpperCase() === "OK"
  );

  return json(
    {
      ok: bridge.response.ok && allFiveOk,
      task_id: taskId,
      mode,
      providers
    },
    bridge.response.ok && allFiveOk ? 200 : 502
  );
}
