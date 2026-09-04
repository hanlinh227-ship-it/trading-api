// Compatibility surface retained so existing scheduler/controller routes do not break.
// All trading authority now belongs to the BTC-only hyperscale engine.
import {runBtcHyperscale,getBtcHyperscaleState,BTC_HYPERSCALE_ENGINE_VERSION} from "./bybit-btc-engine.js";

export async function runBybitAutoV1(env,opts={}){return runBtcHyperscale(env,opts);}
export async function getBybitAutoV1State(env){return getBtcHyperscaleState(env);}
export const BYBIT_AUTO_V1_COMPAT_VERSION=BTC_HYPERSCALE_ENGINE_VERSION;
