// V11 symbol catalog intentionally follows the proven V77/V78 scan universe.
export const V11_SYMBOLS=Object.freeze({
 forex:Object.freeze([
  'AUDCAD','AUDCHF','AUDJPY','AUDNZD','AUDUSD','CADCHF','CADJPY','CHFJPY',
  'EURAUD','EURCAD','EURCHF','EURGBP','EURJPY','EURNZD','EURUSD',
  'GBPAUD','GBPCAD','GBPCHF','GBPJPY','GBPNZD','GBPUSD',
  'NZDCAD','NZDCHF','NZDJPY','NZDUSD','USDCAD','USDCHF','USDJPY'
 ]),
 crypto:Object.freeze([
  'BTCUSDT','ETHUSDT','SOLUSDT','HYPEUSDT','SHIBUSDT','TRXUSDT','XRPUSDT','AAVEUSDT','ADAUSDT','ALGOUSDT','APTUSDT','ARBUSDT','ATOMUSDT','AVAXUSDT',
  'BCHUSDT','BONKUSDT','CRVUSDT','DOGEUSDT','DOTUSDT','ETCUSDT','FILUSDT','FLOKIUSDT','HBARUSDT','INJUSDT','JTOUSDT','JUPUSDT','KAITOUSDT','LDOUSDT','LINKUSDT',
  'LTCUSDT','MOODENGUSDT','NEARUSDT','ONDOUSDT','OPUSDT','ORDIUSDT','PENGUUSDT','PEPEUSDT','PNUTUSDT','POLUSDT','POPCATUSDT','RENDERUSDT','SUSDT','STXUSDT',
  'SUIUSDT','TAOUSDT','TIAUSDT','TRUMPUSDT','UNIUSDT','WIFUSDT','WLDUSDT','AIXBTUSDT','ASTERUSDT','FARTCOINUSDT','GRASSUSDT','IPUSDT','LITUSDT','PUMPUSDT','VIRTUALUSDT','XPLUSDT','ZECUSDT'
 ]),
 metal:Object.freeze(['XAUUSD','XAGUSD']),
 index:Object.freeze(['NAS100','US30','US500','DEX','JP225'])
});
export function symbolsForMarket(market){return V11_SYMBOLS[String(market||'').toLowerCase()]||[];}
export function marketForSymbol(symbol){const s=String(symbol||'').toUpperCase().replace(/[^A-Z0-9]/g,'');for(const [m,rows] of Object.entries(V11_SYMBOLS))if(rows.includes(s))return m;return null;}
export function displaySymbol(symbol,market){const s=String(symbol||'').toUpperCase();return market==='crypto'&&s.endsWith('USDT')?s.slice(0,-4):s;}
