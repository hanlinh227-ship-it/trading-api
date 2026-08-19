import fs from 'node:fs';
const ip='cloudflare-worker/index.js',ep='cloudflare-worker/engine-v77168.js',vp='.github/workflows/validate-cloudflare-v77.yml';
let i=fs.readFileSync(ip,'utf8'),e=fs.readFileSync(ep,'utf8'),v=fs.readFileSync(vp,'utf8');
const must=(src,old,neu,label)=>{if(!src.includes(old))throw new Error('missing '+label);return src.replace(old,neu);};
i=must(i,'const VERSION="V77.18.38",SERVICE="Trading V77.18.38 Repair + Deploy Sync";\nconst RELEASE_NAME="Repair + Deploy Sync";','const VERSION="V77.18.43",SERVICE="Trading V77.18.43 Legacy Cleanup + Version Sync";\nconst RELEASE_NAME="Legacy Cleanup + Version Sync";','index version');
e=e.replace('⏳ HUB đang QUÉT MỚI Crypto + Forex + Metal + Futures...','⏳ HUB legacy đã tắt quét chung. Mở menu để chọn Forex / Crypto / Metal / Index Cash riêng.');
e=e.replace('else if(cb==="hub"||text==="/hub")await sendHub(env,chatId);','else if(cb==="hub"||text==="/hub")await sendText(env,"🏠 Global scan đã tắt. Chọn từng thị trường trong Hub mới.",chatId,baseKeyboard());');
// Legacy shared Live callbacks from old Telegram messages must never trigger cross-market state reads.
e=e.replace('else if(cb==="live"||text==="/live")await sendText(env,booksSummary(await getBooksLive(env)),chatId,baseKeyboard());','else if(cb==="live"||text==="/live")await sendText(env,"📚 Live chung đã tắt. Chọn Live riêng theo từng thị trường trong Hub mới.",chatId,baseKeyboard());');
// Keep old symbol selector only as a redirect selector, never analyze or scan all markets.
e=e.replace('else if(cb==="symbols")await sendText(env,"🔎 Chọn thị trường để tìm từng symbol:",chatId,symbolMarketKeyboard());','else if(cb==="symbols")await sendText(env,"🔎 Symbol chung đã tắt. Chọn đúng thị trường:",chatId,symbolMarketKeyboard());');
v=v.replace("locks(index,['V77.18.38','Repair + Deploy Sync'","locks(index,['V77.18.43','Legacy Cleanup + Version Sync'");
v=v.replace("'callback_data:\"symbol:\"+group+\":\"+symbol'],'Signal');","'callback_data:\"symbol:\"+group+\":\"+symbol','Global scan đã tắt','Live chung đã tắt'],'Signal');");
v=v.replaceAll('V77.18.42 Signal Lifecycle Guard validation PASS','V77.18.43 Legacy Cleanup validation PASS');
fs.writeFileSync(ip,i);fs.writeFileSync(ep,e);fs.writeFileSync(vp,v);console.log('V77.18.43 legacy cleanup migration complete');
