import signalHub from "./hub-v11.js";
import {
  handleUnifiedTelegram,
  handleControlApi
} from "./binance-control-plane.js";
import {
  handleMultiAiControl
} from "./multi-ai-control-plane.js";
import {
  handleChatGptMcp
} from "./chatgpt-mcp.js";
import {
  handleGpt5AiAction
} from "./gpt-5ai-action.js";
import {
  telegramApiRequest
} from "./providers/telegram-client.js";

const VERSION = "V11";

const SERVICE =
  "Trading Unified Hub • Signal V11 + Separate Binance Approval";

const SIGNAL_V11_MAINTENANCE = true;

function isTelegramWebhook(req) {
  try {
    return (
      new URL(req.url).pathname === "/telegram/webhook" &&
      req.method === "POST"
    );
  } catch {
    return false;
  }
}

async function telegramOwner(req) {
  if (!isTelegramWebhook(req)) {
    return "NONE";
  }

  try {
    const u = await req.clone().json();

    const cb = String(
      u?.callback_query?.data || ""
    );

    return (
      cb === "binance" ||
      cb.startsWith("binance:")
    )
      ? "BINANCE"
      : "SIGNAL_V11";
  } catch {
    return "SIGNAL_V11";
  }
}

async function maintenanceTelegram(req, env) {
  try {
    const u = await req.clone().json();

    const chat = String(
      u?.callback_query?.message?.chat?.id ??
      u?.message?.chat?.id ??
      env.TELEGRAM_CHAT_ID ??
      ""
    );

    if (chat) {
      await telegramApiRequest(
        env,
        "sendMessage",
        {
          chat_id: chat,
          text:
            "🛠 Signal V11 đang tạm khóa để rà soát " +
            "xung đột runtime/entry/CUT/live-price. " +
            "Không phát lệnh mới cho tới khi validation hoàn tất."
        }
      );
    }
  } catch (e) {
    console.error(
      "V11_MAINTENANCE_TELEGRAM",
      e
    );
  }

  return new Response(
    "OK",
    {
      status: 200
    }
  );
}

export default {
  async fetch(req, env, ctx) {

    /*
     * Existing ChatGPT MCP.
     */
    const mcp =
      await handleChatGptMcp(
        req,
        env
      );

    if (mcp) {
      return mcp;
    }

    /*
     * NEW:
     * Custom GPT Action -> 5AI Council.
     *
     * Endpoint:
     * POST /api/5ai/council
     */
    const gpt5ai =
      await handleGpt5AiAction(
        req,
        env
      );

    if (gpt5ai) {
      return gpt5ai;
    }

    /*
     * Existing GitHub OIDC 5AI control plane.
     */
    const multi =
      await handleMultiAiControl(
        req,
        env
      );

    if (multi) {
      return multi;
    }

    /*
     * Existing Binance/control API.
     */
    const control =
      await handleControlApi(
        req,
        env
      );

    if (control) {
      return control;
    }

    const owner =
      await telegramOwner(req);

    if (owner === "BINANCE") {
      const b =
        await handleUnifiedTelegram(
          req,
          env
        );

      if (b) {
        return b;
      }
    }

    if (
      SIGNAL_V11_MAINTENANCE &&
      owner === "SIGNAL_V11"
    ) {
      return maintenanceTelegram(
        req,
        env
      );
    }

    const url =
      new URL(req.url);

    if (
      SIGNAL_V11_MAINTENANCE &&
      url.pathname.startsWith("/v11/")
    ) {
      return new Response(
        JSON.stringify(
          {
            ok: false,
            status:
              "SIGNAL_V11_MAINTENANCE",
            reason:
              "RUNTIME_CONFLICT_AUDIT_IN_PROGRESS"
          },
          null,
          2
        ),
        {
          status: 503,
          headers: {
            "content-type":
              "application/json; charset=utf-8",
            "cache-control":
              "no-store"
          }
        }
      );
    }

    const r =
      await signalHub.fetch(
        req,
        env,
        ctx
      );

    if (owner === "SIGNAL_V11") {
      return r;
    }

    if (url.pathname !== "/status") {
      return r;
    }

    let body;

    try {
      body =
        await r.clone().json();
    } catch {
      return r;
    }

    return new Response(
      JSON.stringify(
        {
          ...body,

          version: VERSION,
          service: SERVICE,

          signalOnlySourceOfTruth:
            "V11",

          signalV11Maintenance:
            SIGNAL_V11_MAINTENANCE,

          telegramRootOwner:
            "SIGNAL_V11",

          instrumentSpecificStrategies:
            true,

          structureAwareRisk:
            true,

          twelveDataPlan:
            "GROW_55",

          cloudflareRuntimeAuthority:
            true,

          deepSeekApiNative:
            true,

          claudeMaxRole:
            "HUMAN_ASSISTED_REVIEW",

          chatgptPlusRole:
            "COENGINEER_AUDIT",

          legacySignalVersions:
            "COMPATIBILITY_TRACKING_ONLY",

          binanceAutoProjectSeparate:
            true,

          multiAiGateway:
            "VPC_OIDC_CONTROL_PLANE",

          chatgptMcp:
            "/mcp",

          /*
           * New Custom GPT Action endpoint.
           */
          gpt5AiCouncil:
            "/api/5ai/council"
        },
        null,
        2
      ),
      {
        status: r.status,
        headers: {
          "content-type":
            "application/json; charset=utf-8",
          "cache-control":
            "no-store"
        }
      }
    );
  },

  async scheduled(event, env, ctx) {
    if (SIGNAL_V11_MAINTENANCE) {
      console.log(
        "SIGNAL_V11_MAINTENANCE_SCHEDULED_SKIP"
      );

      return;
    }

    return signalHub.scheduled?.(
      event,
      env,
      ctx
    );
  }
};
