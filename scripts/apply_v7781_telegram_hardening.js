const fs = require('fs');
const path = 'cloudflare-worker/index.js';
let s = fs.readFileSync(path, 'utf8');

function mustReplace(from,to,label){
  if(!s.includes(from)) throw new Error(`Missing patch target: ${label}`);
  s=s.replace(from,to);
}

s=s.replaceAll('V77.8.0','V77.8.1');
s=s.replaceAll('v778:news_clear:','v7781:news_clear:');

mustReplace(
`function normalizeBooks(v){const b=emptyBooks();if(!v||typeof v!=="object")return b;for(const g of Object.keys(GROUPS))for(const k of ["marketActive","limitActive","limitPending","watch"])if(Array.isArray(v?.[g]?.[k]))b[g][k]=v[g][k];b.updatedAt=v.updatedAt||Date.now();return b;}`,
`function validExecutablePosition(p,group){
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
    // V77.8+ never carries executable Forex/Metal positions without a broker execution feed.
    // This also purges stale legacy entries that produced TP ? in Telegram.
    if(g==="crypto"){
      b[g].marketActive=Array.isArray(src.marketActive)?src.marketActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxMarketActive):[];
      b[g].limitActive=Array.isArray(src.limitActive)?src.limitActive.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxLimitActive):[];
      b[g].limitPending=Array.isArray(src.limitPending)?src.limitPending.filter(p=>validExecutablePosition(p,g)).slice(0,CONFIG.maxPendingLimit):[];
    }
    b[g].watch=Array.isArray(src.watch)?src.watch.filter(w=>validWatch(w,g)).slice(0,CONFIG.maxWatch):[];
  }
  b.updatedAt=v.updatedAt||Date.now();return b;
}`,
'normalizeBooks cleanup'
);

mustReplace(
`async function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text,reply_markup,disable_web_page_preview:true});}`,
`function telegramSafeText(text){const x=String(text??"");return x.length<=3900?x:x.slice(0,3860)+"\\n… nội dung đã được rút gọn";}
async function sendText(env,text,chatId=env.TELEGRAM_CHAT_ID,reply_markup){return telegram(env,"sendMessage",{chat_id:chatId,text:telegramSafeText(text),reply_markup,disable_web_page_preview:true});}`,
'safe Telegram text'
);

mustReplace(
`function fmtPx(v){const n=Number(v);return Number.isFinite(n)?n.toPrecision(7):"?";}
function posLine(p){return \`${'${p.symbol} ${sideText(p.side)} | E ${fmtPx(p.entry)} | SL ${fmtPx(p.sl)} | TP ${fmtPx(p.tp)}'}\`;}
function watchLine(w){let x=\`${'${w.symbol} ${sideText(w.side)} | ${w.reason||"CHỜ XÁC NHẬN"}'}\`;if(w.planned)x+=\` | E~${'${fmtPx(w.planned.entry)}'} SL~${'${fmtPx(w.planned.sl)}'} TP~${'${fmtPx(w.planned.targetRR===2?w.planned.tp2:w.planned.tp1)}'}\`;return x;}`,
`function fmtPx(v){const n=Number(v);if(!Number.isFinite(n))return "—";if(Math.abs(n)>=1000)return n.toFixed(2);if(Math.abs(n)>=10)return n.toFixed(4);if(Math.abs(n)>=1)return n.toFixed(5);return n.toPrecision(6);}
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
function watchLine(w){let x=\`${'${w.symbol} ${sideText(w.side)} • ${reasonText(w.reason)}'}\`;if(w.planned)x+=\`\\n   ↳ E~${'${fmtPx(w.planned.entry)}'} • SL~${'${fmtPx(w.planned.sl)}'} • TP~${'${fmtPx(w.planned.targetRR===2?w.planned.tp2:w.planned.tp1)}'}\`;return x;}`,
'UI reason translation'
);

mustReplace(
`  if(run){
    if(run.status==="RATE_BUDGET_WAIT"){L.push(\`⏱ Twelve Data còn ${'${run.diagnostics?.tdCreditsLeft??"?"}'} credit; cần ${'${run.diagnostics?.tdCreditsRequired??"?"}'}. Thử lại sau ~${'${run.retryAfterSec??60}'}s.\`);return L.join("\\n");}
    L.push(\`🔍 Quét: ${'${run.requested}'} | Deep OK: ${'${run.deepOk}'}/${'${run.deepRequested}'} | Mới: ${'${run.newCount}'}\`,\`🧪 Coverage: ${'${run.broadOk}'}/${'${run.requested}'}\`);
    const rs=run.analyses.map(a=>\`${'${a.symbol}'}=${'${a.status}'}${'${a.reason?`(${a.reason})`:""}'}\`).join(" | ");if(rs)L.push(\`📍 ${'${rs}'}\`);
  }`,
`  if(run){
    if(run.status==="RATE_BUDGET_WAIT"){L.push("",\`⏱ Twelve Data đang hồi quota • còn ${'${run.diagnostics?.tdCreditsLeft??"?"}'} / cần ${'${run.diagnostics?.tdCreditsRequired??"?"}'} • thử lại ~${'${run.retryAfterSec??60}'}s\`);return L.join("\\n");}
    L.push("",\`🔎 Quét ${'${run.requested}'} • Coverage ${'${run.broadOk}'}/${'${run.requested}'} • Deep ${'${run.deepOk}'}/${'${run.deepRequested}'} • Lệnh mới ${'${run.newCount}'}\`);
  }`,
'concise summary diagnostics'
);

mustReplace(
`  h.top.forEach((a,i)=>{let line=\`${'${i+1}. ${a.symbol} ${sideText(a.side)} | ${a.status}${a.reason?` • ${a.reason}`:""}'}\`;if(a.planned)line+=\` | E~${'${fmtPx(a.planned.entry)}'} SL~${'${fmtPx(a.planned.sl)}'} TP~${'${fmtPx(a.planned.targetRR===2?a.planned.tp2:a.planned.tp1)}'}\`;if(a.quote?.source||a.source)line+=\` | ${'${a.quote?.source||a.source}'}\`;L.push(line);});`,
`  h.top.slice(0,5).forEach((a,i)=>{let line=\`${'${i+1}. ${a.symbol} ${sideText(a.side)} • ${a.status==="WATCH"?reasonText(a.reason):a.status}'}\`;if(a.planned)line+=\`\\n   ↳ E~${'${fmtPx(a.planned.entry)}'} • SL~${'${fmtPx(a.planned.sl)}'} • TP~${'${fmtPx(a.planned.targetRR===2?a.planned.tp2:a.planned.tp1)}'}\`;if(a.quote?.source||a.source)line+=\`\\n   ↳ ${'${a.quote?.source||a.source}'}\`;L.push(line);});`,
'clean hub summary'
);

mustReplace(
`function booksSummary(books){const L=["📚 BOOKS"];for(const g of ["forex","crypto","metal"]){const b=books[g];L.push(\`${'${groupTitle(g)}'} • M ${'${b.marketActive.length}'} • L ${'${b.limitActive.length}'} • Pending ${'${b.limitPending.length}'} • Watch ${'${b.watch.length}'}\`);}return L.join("\\n");}`,
`function booksSummary(books){const L=["📚 BOOKS — trạng thái hiện tại",""];for(const g of ["forex","crypto","metal"]){const b=books[g];L.push(\`${'${groupTitle(g)}'} • Market ${'${b.marketActive.length}'} • Limit ${'${b.limitActive.length}'} • Chờ ${'${b.limitPending.length}'} • Watch ${'${b.watch.length}'}\`);}L.push("","ℹ️ Forex/Metal chỉ có WATCH cho tới khi có broker bid/ask thực.");return L.join("\\n");}`,
'books summary clarification'
);

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.8.1 Telegram UI/data hardening.');
