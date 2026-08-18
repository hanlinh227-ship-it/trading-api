const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');

function replaceRange(start,end,replacement,label){
  const a=s.indexOf(start);if(a<0)throw new Error(`Missing start ${label}`);
  const b=s.indexOf(end,a);if(b<0)throw new Error(`Missing end ${label}`);
  s=s.slice(0,a)+replacement+s.slice(b);
}
function mustReplace(from,to,label){if(!s.includes(from))throw new Error(`Missing ${label}`);s=s.replace(from,to);}

s=s.replaceAll('V77.8.0','V77.8.1').replaceAll('v778:news_clear:','v7781:news_clear:');

replaceRange('function normalizeBooks(', '\nasync function getBooks', `function validExecutablePosition(p,group){
  if(group!=="crypto"||!p||typeof p!=="object")return false;
  if(!CRYPTO.includes(norm(p.symbol)))return false;
  if(!["LONG","SHORT"].includes(p.side))return false;
  return [p.entry,p.sl,p.tp].every(v=>Number.isFinite(Number(v))&&Number(v)>0);
}
function validWatch(w,group){return !!w&&typeof w==="object"&&GROUPS[group].includes(norm(w.symbol));}
function normalizeBooks(v){
  const b=emptyBooks();if(!v||typeof v!=="object")return b;
  for(const g of Object.keys(GROUPS)){
    const src=v?.[g]||{};
    if(g==="crypto"){
      b[g].marketActive=Array.isArray(src.marketActive)?src.marketActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxMarketActive):[];
      b[g].limitActive=Array.isArray(src.limitActive)?src.limitActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxLimitActive):[];
      b[g].limitPending=Array.isArray(src.limitPending)?src.limitPending.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxPendingLimit):[];
    }
    b[g].watch=Array.isArray(src.watch)?src.watch.filter(w=>validWatch(w,g)).slice(0,CONFIG.maxWatch):[];
  }
  b.updatedAt=v.updatedAt||Date.now();return b;
}
`, 'normalize books');

mustReplace(
'async function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}',
'function telegramSafeText(text){const x=String(text??"");return x.length<=3900?x:x.slice(0,3860)+"\\n… nội dung đã được rút gọn";}\nasync function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text:telegramSafeText(text),reply_markup,disable_web_page_preview:true});}',
'sendText');

replaceRange('function fmtPx(', '\nfunction summary(', `function fmtPx(v){const n=Number(v);if(!Number.isFinite(n))return "—";if(Math.abs(n)>=1000)return n.toFixed(2);if(Math.abs(n)>=10)return n.toFixed(4);if(Math.abs(n)>=1)return n.toFixed(5);return n.toPrecision(6);}
function reasonText(r){return ({
  HTF_ALIGNMENT_REQUIRED:"Chờ D1/H4/H1 đồng thuận",
  M15_LOCATION_REQUIRED:"Chờ giá vào vùng M15 đẹp",
  M5_MSS_DISPLACEMENT_RETEST_REQUIRED:"Chờ trigger M5 hoàn chỉnh",
  STRUCTURAL_SL_REQUIRED:"Chưa có SL cấu trúc hợp lệ",
  H1_CLEAN_ROOM_REQUIRED:"Khoảng chạy chưa đủ",
  NEWS_CONTEXT_REQUIRED:"Chờ xác nhận tin/context",
  EXECUTION_QUOTE_REQUIRED:"Chờ bid/ask broker thực",
  FINAL_QUOTE_REQUIRED:"Chờ giá execution mới",
  FINAL_QUOTE_STALE:"Giá execution đã cũ",
  EXECUTION_COST_TOO_HIGH:"Spread/chi phí quá cao",
  TIMEFRAME_DATA_REQUIRED:"Thiếu dữ liệu timeframe",
  ANALYSIS_DATA_UNAVAILABLE:"Dữ liệu phân tích tạm thiếu",
  EXCHANGE_DEEP_UNAVAILABLE:"Sàn tạm thiếu dữ liệu sâu"
})[r]||"Chờ thêm xác nhận";}
function posLine(p){return \`${'${p.symbol} ${sideText(p.side)} • E ${fmtPx(p.entry)} • SL ${fmtPx(p.sl)} • TP ${fmtPx(p.tp)}'}\`;}
function watchLine(w){let x=\`${'${w.symbol} ${sideText(w.side)} • ${reasonText(w.reason)}'}\`;if(w.planned)x+=\`\\n   ↳ E~${'${fmtPx(w.planned.entry)}'} • SL~${'${fmtPx(w.planned.sl)}'} • TP~${'${fmtPx(w.planned.targetRR===2?w.planned.tp2:w.planned.tp1)}'}\`;return x;}
`, 'format UI');

replaceRange('function summary(', '\nasync function sendGroup', `function summary(group,books,run=null){
  const b=books[group],L=[groupTitle(group),"",\`🟢 MARKET ${'${b.marketActive.length}'}/${'${CONFIG.maxMarketActive}'}\`];
  if(b.marketActive.length)b.marketActive.forEach((p,i)=>L.push(\`${'${i+1}. ${posLine(p)}'}\`));else L.push("Trống");
  L.push("",\`🔵 LIMIT ĐÃ KHỚP ${'${b.limitActive.length}'}/${'${CONFIG.maxLimitActive}'}\`);if(b.limitActive.length)b.limitActive.forEach((p,i)=>L.push(\`${'${i+1}. ${posLine(p)}'}\`));else L.push("Trống");
  L.push("",\`🟡 LIMIT CHỜ ${'${b.limitPending.length}'}/${'${CONFIG.maxPendingLimit}'}\`);if(b.limitPending.length)b.limitPending.forEach((p,i)=>L.push(\`${'${i+1}. ${posLine(p)}'}\`));else L.push("Trống");
  L.push("",\`👀 WATCH ${'${b.watch.length}'}/${'${CONFIG.maxWatch}'}\`);if(b.watch.length)b.watch.forEach((w,i)=>L.push(\`${'${i+1}. ${watchLine(w)}'}\`));else L.push("Trống");
  if(run){
    if(run.status==="RATE_BUDGET_WAIT"){L.push("",\`⏱ Twelve Data đang hồi quota • còn ${'${run.diagnostics?.tdCreditsLeft??"?"}'} / cần ${'${run.diagnostics?.tdCreditsRequired??"?"}'} • thử lại ~${'${run.retryAfterSec??60}'}s\`);return L.join("\\n");}
    L.push("",\`🔎 Quét ${'${run.requested}'} • Coverage ${'${run.broadOk}'}/${'${run.requested}'} • Deep ${'${run.deepOk}'}/${'${run.deepRequested}'} • Lệnh mới ${'${run.newCount}'}\`);
  }
  return L.join("\\n");
}
`, 'summary');

replaceRange('function hubSummary(', '\nasync function sendHub', `function hubSummary(h){
  const L=[\`🧭 TRADING HUB ${'${CONFIG.version}'}\`,"","Top setup hiện tại:"];
  if(!h.top.length)L.push("Chưa có setup đủ tốt.");
  h.top.slice(0,5).forEach((a,i)=>{let line=\`${'${i+1}. ${a.symbol} ${sideText(a.side)} • ${a.status==="WATCH"?reasonText(a.reason):a.status}'}\`;if(a.planned)line+=\`\\n   ↳ E~${'${fmtPx(a.planned.entry)}'} • SL~${'${fmtPx(a.planned.sl)}'} • TP~${'${fmtPx(a.planned.targetRR===2?a.planned.tp2:a.planned.tp1)}'}\`;if(a.quote?.source||a.source)line+=\`\\n   ↳ ${'${a.quote?.source||a.source}'}\`;L.push(line);});
  L.push("","⚠️ MARKET/LIMIT chỉ hiện khi toàn bộ gate + execution quote PASS.");
  for(const g of ["forex","crypto","metal"]){const r=h.runs[g];L.push(\`${'${groupTitle(g)}'}: ${'${r.status==="RATE_BUDGET_WAIT"?"đợi quota":`${r.broadOk}/${r.requested} coverage • deep ${r.deepOk}/${r.deepRequested}`}'}\`);}
  return L.join("\\n");
}
`, 'hub summary');

replaceRange('function booksSummary(', '\n\nasync function lifecycle', `function booksSummary(books){
  const L=["📚 BOOKS — trạng thái hiện tại",""];
  for(const g of ["forex","crypto","metal"]){const b=books[g];L.push(\`${'${groupTitle(g)}'} • Market ${'${b.marketActive.length}'} • Limit ${'${b.limitActive.length}'} • Chờ ${'${b.limitPending.length}'} • Watch ${'${b.watch.length}'}\`);}
  L.push("","ℹ️ Forex/Metal chỉ có WATCH cho tới khi có broker bid/ask thực.");return L.join("\\n");
}
`, 'books summary');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.8.1 Telegram UI/data hardening.');
