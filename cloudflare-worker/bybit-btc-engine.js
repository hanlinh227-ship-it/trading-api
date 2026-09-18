// Compatibility facade.
//
// The canonical BTCUSDT execution engine lives in bybit-symbol-engine.js.
// Keeping this filename preserves existing monitor/hub imports without retaining
// a second copy of trading logic or a second execution authority.
export {
  runBtcHyperscale,
  getBtcHyperscaleState,
  BTC_HYPERSCALE_ENGINE_VERSION,
} from './bybit-symbol-engine.js';
