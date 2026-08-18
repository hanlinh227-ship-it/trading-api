const fs=require('fs');
const path='cloudflare-worker/index.js';
let s=fs.readFileSync(path,'utf8');
function mustReplace(from,to,label){if(!s.includes(from))throw new Error('Missing '+label);s=s.replace(from,to);}

s=s.replaceAll('V77.10.0','V77.10.1');
s=s.replace('Trading V77.10.1 Adaptive Symbol Intelligence Hub','Trading V77.10.1 Adaptive Entry Intelligence Hub');

mustReplace('deepRequested:CONFIG.maxCandidates,deepOk:analyses.filter(a=>a.ok!==false).length','deepRequested:Math.min(CONFIG.maxCandidates,broad.rows.length),deepOk:analyses.filter(a=>a.ok!==false).length','accurate deepRequested');

mustReplace('M5_MSS_DISPLACEMENT_RETEST_REQUIRED:"Chờ trigger M5"','M5_MSS_DISPLACEMENT_RETEST_REQUIRED:"Chờ trigger M5 phù hợp profile"','adaptive reason text');

const oldWatch='function watchLine(w){let x=`${w.symbol} ${sideText(w.side)} • ${reasonText(w.reason)}`;if(Number.isFinite(w.score))x+=` • ${w.score}/100`;if(w.planned)x+=`\n   ↳ E~${fmtPx(w.planned.entry)} • SL~${fmtPx(w.planned.sl)} • TP~${fmtPx(w.planned.tp2||w.planned.tp1)} • RR~${Number(w.planned.targetRR||0).toFixed(2)}`;if(w.method?.profile)x+=`\n   ↳ ${w.method.profile}`;return x;}';
const newWatch='function watchLine(w){let x=`${w.symbol} ${sideText(w.side)} • ${reasonText(w.reason)}`;if(Number.isFinite(w.score))x+=` • ${w.score}/100`;if(w.planned){const tag=w.planned.indicative?"Tham khảo":"Kế hoạch";x+=`\n   ↳ ${tag}: E~${fmtPx(w.planned.entry)} • SL~${fmtPx(w.planned.sl)} • TP~${fmtPx(w.planned.tp2||w.planned.tp1)} • RR~${Number(w.planned.targetRR||0).toFixed(2)}`;if(w.planned.entryStyle)x+=`\n   ↳ Entry style: ${w.planned.entryStyle}`;}if(w.method?.profile)x+=`\n   ↳ Method: ${w.method.profile}`;return x;}';
mustReplace(oldWatch,newWatch,'watch UI');

const insertAfter=newWatch+'\n';
const singleFn=[
'function singleAnalysisText(a){',
'  if(!a)return "⛔ Không có kết quả phân tích.";',
'  if(a.ok===false)return `⛔ ${a.symbol||"SYMBOL"} • ${reasonText(a.reason)}\\n${a.error?"Chi tiết: "+a.error:""}`;',
'  const L=[`🔎 ${a.symbol} • ${stageText(a)}${Number.isFinite(a.score)?" • "+a.score+"/100":""}`,`Hướng: ${sideText(a.side)}`];',
'  if(a.method?.profile)L.push(`Method: ${a.method.profile}`);',
'  if(a.entryPolicy?.profile)L.push(`Profile engine: ${a.entryPolicy.profile}`);',
'  if(a.status==="MARKET"||a.status==="LIMIT"){L.push("",`✅ LỆNH EXECUTABLE ${a.status}`,`Entry ${fmtPx(a.entry)} • SL ${fmtPx(a.sl)}`,`TP1 ${fmtPx(a.tp1)} • TP2 ${fmtPx(a.tp2)} • RR ${Number(a.targetRR||0).toFixed(2)}`);}',
'  else if(a.planned){const tag=a.planned.indicative?"📐 ENTRY THAM KHẢO — chưa phải lệnh":"🎯 KẾ HOẠCH ENTRY";L.push("",tag,`E~${fmtPx(a.planned.entry)} • SL~${fmtPx(a.planned.sl)}`,`TP1~${fmtPx(a.planned.tp1)} • TP2~${fmtPx(a.planned.tp2)} • RR~${Number(a.planned.targetRR||0).toFixed(2)}`);if(a.planned.entryStyle)L.push(`Style: ${a.planned.entryStyle}`);}',
'  L.push("",`Trạng thái: ${a.status==="WATCH"?reasonText(a.reason):a.status}`);if(a.source)L.push(`Data: ${a.source}`);',
'  return L.join("\\n");',
'}',
''
].join('\n');
mustReplace(insertAfter,insertAfter+singleFn,'single analysis formatter');

// Improve Hub planned-entry labeling.
mustReplace('if(a.planned)line+=`\\n   ↳ E~${fmtPx(a.planned.entry)} • SL~${fmtPx(a.planned.sl)} • TP~${fmtPx(a.planned.tp2||a.planned.tp1)} • RR~${Number(a.planned.targetRR||0).toFixed(2)}`;','if(a.planned){const tag=a.planned.indicative?"Entry tham khảo":"Kế hoạch";line+=`\\n   ↳ ${tag}: E~${fmtPx(a.planned.entry)} • SL~${fmtPx(a.planned.sl)} • TP~${fmtPx(a.planned.tp2||a.planned.tp1)} • RR~${Number(a.planned.targetRR||0).toFixed(2)}`;if(a.planned.entryStyle)line+=`\\n   ↳ ${a.planned.entryStyle}`;}','hub entry labeling');

// Preserve adaptive context when rechecking after manual news clearance.
const oldNews='let a;if(group==="crypto"){try{const b=await cryptoDeepBundle(symbol);a=await deepAnalyze(symbol,env,b.candles,b.quote,b.source);}catch(e){a={ok:false,status:"DATA_BLOCK",symbol:norm(symbol),reason:"EXCHANGE_DEEP_UNAVAILABLE",error:e?.message||String(e)};}}else a=await deepAnalyze(symbol,env);';
mustReplace(oldNews,'const a=await runSymbol(symbol,env);','news recheck through runSymbol');

// Add /coin and /analyze command before books/status fallback.
const cmdAnchor='  }else if(cb==="books")await sendText(env,booksSummary(await getBooks(env)),chatId,baseKeyboard());';
const cmdBlock=[
'  }else {',
'    const cm=text.trim().match(/^\\/(?:coin|analyze)\\s+([A-Za-z0-9]+)$/i);',
'    if(cm){',
'      let symbol=norm(cm[1]);if(CRYPTO_BASE.includes(symbol))symbol=symbol+"USDT";',
'      await sendText(env,`⏳ Đang phân tích ${symbol} theo profile riêng...`,chatId);',
'      const a=await runSymbol(symbol,env),type=marketType(symbol);',
'      if(type!=="unknown"){const books=await getBooks(env);const added=fillBooks(type,books,[a]);if(added.length||a.status==="WATCH")await saveBooks(env,books);}',
'      await sendText(env,singleAnalysisText(a),chatId,baseKeyboard());',
'    }else if(cb==="books")await sendText(env,booksSummary(await getBooks(env)),chatId,baseKeyboard());',
'    else if(cb==="status"||text==="/status")await sendText(env,`⚙️ SYSTEM STATUS\\nVersion: ${CONFIG.version}\\nKV: ${env.TRADING_STATE?"ONLINE":"MISSING"}\\nTwelve Data: ${env.TWELVE_DATA_API_KEY?"CONFIGURED":"MISSING"}\\nTelegram: CONNECTED\\nHub: ADAPTIVE\\nCrypto: 61 symbol • exact 5TF + bid/ask\\nLệnh: chỉ executable khi đủ gate\\nGõ /coin BTC hoặc /analyze KAITOUSDT để phân tích riêng\\nNews gate: STRICT\\nV73: FROZEN PRIOR`,chatId,baseKeyboard());',
'    else await sendText(env,`🤖 TRADING HUB ${CONFIG.version}\\nChọn HUB/thị trường hoặc gõ /coin BTC để phân tích riêng.`,chatId,baseKeyboard());',
'  }',
].join('\n');
// Replace books + status + final else chain as one range.
const chainStart='  }else if(cb==="books")await sendText(env,booksSummary(await getBooks(env)),chatId,baseKeyboard());';
const chainEnd='  return json({ok:true});';
const a=s.indexOf(chainStart);if(a<0)throw new Error('Missing Telegram fallback chain');const b=s.indexOf(chainEnd,a);if(b<0)throw new Error('Missing Telegram return');s=s.slice(0,a)+cmdBlock+'\n'+s.slice(b);

// Menu hint.
s=s.replaceAll('Chọn HUB hoặc thị trường:','Chọn HUB/thị trường hoặc gõ /coin BTC:');

fs.writeFileSync(path,s,'utf8');
console.log('Applied V77.10.1 Hub polish + direct symbol analysis');
