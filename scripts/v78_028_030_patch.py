from pathlib import Path
import re, sys

p=Path('cloudflare-worker/engine-v77168.js')
s=p.read_text()
phase=sys.argv[1]

if phase=='028':
    old='function baseKeyboard(){return {inline_keyboard:[[{text:"📡 SIGNAL",callback_data:"signal"}],[{text:"🏦 PROP",callback_data:"prop"},{text:"👤 CÁ NHÂN",callback_data:"personal"}],[{text:"🔎 SYMBOL",callback_data:"symbols"}],[{text:"📊 STATUS",callback_data:"status"},{text:"📚 LIVE ORDERS",callback_data:"live"}]]};}'
    new='function baseKeyboard(){return {inline_keyboard:[[{text:"📡 SIGNAL",callback_data:"signal"}],[{text:"🔎 SYMBOL",callback_data:"symbols"}],[{text:"📊 STATUS",callback_data:"status"},{text:"📚 LIVE ORDERS",callback_data:"live"}]]};}'
    assert s.count(old)==1
    s=s.replace(old,new,1)
    for name in ('propKeyboard','personalKeyboard'):
        s,n=re.subn(rf'^function {name}\(\).*?$','',s,count=1,flags=re.M); assert n==1
    for pat in [r'^  else if\(cb==="prop"\).*?;$',r'^  else if\(cb==="prop:hyro"\).*?;$',r'^  else if\(cb==="prop:breakout"\).*?;$',r'^  else if\(cb==="prop:orders"\|\|cb==="prop:risk"\).*?;$',r'^  else if\(cb==="personal"\).*?;$',r'^  else if\(cb\?\.startsWith\("personal:"\)\).*?;$']:
        s,n=re.subn(pat,'',s,count=1,flags=re.M); assert n==1,(pat,n)
    m=re.search(r'^(function reasonText\(r\)\{.*\})$',s,flags=re.M); assert m
    helper='\nconst SESSION_VI={LONDON_ACTIVE:"phiên London",LONDON_NY_OVERLAP:"giao thoa London-New York",NEW_YORK_ACTIVE:"phiên New York",ASIA_ACTIVE:"phiên châu Á",OFF_PEAK:"ngoài giờ cao điểm",TOKYO_ACTIVE:"phiên Tokyo",TOKYO_OFF:"ngoài phiên Tokyo",EUROPE_ACTIVE:"phiên châu Âu",EUROPE_OFF:"ngoài phiên châu Âu",US_CASH_WINDOW:"phiên Mỹ",US_OFF:"ngoài phiên Mỹ"};\nfunction whyNowVi(a){const parts=[],sess=SESSION_VI[a?.context?.session];if(sess)parts.push(sess);if(a?.method?.profile)parts.push("phương pháp "+a.method.profile);const actionableSet=["MARKET","LIMIT","MARKET_SIGNAL","MARKET_PLAN","LIMIT_PLAN"];if(actionableSet.includes(a?.status))parts.push("đủ điều kiện kỹ thuật để vào lệnh");else{const rsn=reasonText(a?.reason);if(rsn)parts.push(rsn);}return parts.length?parts.join(" • "):"Chưa đủ dữ liệu để giải thích";}'
    s=s[:m.end()]+helper+s[m.end():]
    needle='const eiShadow=buildEntryIntelligenceShadow(a);if(eiShadow)L.push(`Quality: ${eiShadow.quality.grade} (${eiShadow.quality.score}/100)${eiShadow.promotion.allowed===false?" • ⚠️ "+eiShadow.promotion.reasons.join(","):""}`);'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'\n  L.push(`WHY NOW: ${whyNowVi(a)}`);',1)
    oldidx='async function tdIndexQuote(symbol,env){const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,p=await tdFetch("time_series",{symbol:ps,type:"Index",interval:"1min",outputsize:"2",order:"DESC",timezone:"UTC"},env),node=tdIndexNode(p);assertTdIndexIdentity(s,node);const c=tdCandlesFromNode(node,"1min"),last=c?.at(-1),price=num(last?.close);if(!(price>0)||!validIndexPrice(s,price))throw new Error(`Twelve Data invalid native index value ${s}/${ps}: ${price}`);return {source:"Twelve Data Native Index",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:last?.timestamp||null,quoteAgeSec:last?.timestamp?Math.max(0,nowSec()-last.timestamp-60):null,fresh:true,bid:null,ask:null,executionVerified:false,analysisOnly:true,assetType:node?.meta?.type||"Index"};}'
    newidx='async function tdIndexQuote(symbol,env){const s=norm(symbol),ps=INDEX_PROVIDER[s]||s,p=await tdFetch("time_series",{symbol:ps,type:"Index",interval:"1min",outputsize:"2",order:"DESC",timezone:"UTC"},env),node=tdIndexNode(p);assertTdIndexIdentity(s,node);const c=tdCandlesFromNode(node,"1min"),last=c?.at(-1),price=num(last?.close);if(!(price>0)||!validIndexPrice(s,price))throw new Error(`Twelve Data invalid native index value ${s}/${ps}: ${price}`);const age=last?.timestamp?Math.max(0,nowSec()-last.timestamp-60):null;return {source:"Twelve Data Native Index",requestedSymbol:s,providerSymbol:ps,price,providerTimestamp:last?.timestamp||null,quoteAgeSec:age,fresh:age!==null&&age<=CONFIG.maxQuoteAgeSec,bid:null,ask:null,executionVerified:false,analysisOnly:true,assetType:node?.meta?.type||"Index"};}'
    assert s.count(oldidx)==1
    s=s.replace(oldidx,newidx,1)
    oldrun='  const maps=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=maps.map(m=>m.get(s)||[]);let q=null;try{q=await tdQuote(s,env);}catch{}const sess=indexSessionBias(s),context={session:sess.label,sessionScore:sess.score,score:Math.min(10,5+sess.score*.8)};const a=await deepAnalyze(s,env,candles,q,q?.source||"Verified native Index",context);if(q)a.analysisQuote=q;return a;'
    newrun='  const maps=await Promise.all(INTERVALS.map(i=>tdBatchCandles([s],i,env,CONFIG.candleOutputSize))),candles=maps.map(m=>m.get(s)||[]);let q=null;try{q=await tdQuote(s,env);}catch{}if(!q){const last=(candles[0]||[]).at(-1),price=num(last?.close);if(validIndexPrice(s,price)){const age=last?.timestamp?Math.max(0,nowSec()-Number(last.timestamp)):null;q={source:"Index completed M5 fallback",requestedSymbol:s,providerSymbol:MASSIVE_INDEX_PROVIDER[s]||INDEX_PROVIDER[s]||s,price,providerTimestamp:last?.timestamp||null,quoteAgeSec:age,fresh:false,bid:null,ask:null,executionVerified:false,analysisOnly:true,fallback:true};}}const sess=indexSessionBias(s),context={session:sess.label,sessionScore:sess.score,instrumentIdentity:"CASH_INDEX",score:Math.min(10,5+sess.score*.8)};const a=await deepAnalyze(s,env,candles,q,q?.source||"Verified native Index",context);if(q)a.analysisQuote=q;return a;'
    assert s.count(oldrun)==1
    s=s.replace(oldrun,newrun,1)
elif phase=='030':
    assert s.count('function whyNowVi')==1
    old='   ↳ Method: ${w.method.profile}`;const ei=buildEntryIntelligenceShadow(w);if(ei)x+=`\n   ↳ Quality: ${ei.quality.grade} (${ei.quality.score}/100)${ei.promotion.allowed===false?" • ⚠️ "+ei.promotion.reasons.join(","):""} • Fresh: ${ei.quote.freshness}`;return x;}'
    new='   ↳ Method: ${w.method.profile}`;const ei=buildEntryIntelligenceShadow(w);if(ei)x+=`\n   ↳ Quality: ${ei.quality.grade} (${ei.quality.score}/100)${ei.promotion.allowed===false?" • ⚠️ "+ei.promotion.reasons.join(","):""} • Fresh: ${ei.quote.freshness}`;x+=`\n   ↳ Why now: ${whyNowVi(w)}`;return x;}'
    assert s.count(old)==1
    s=s.replace(old,new,1)
    old2='const ei=buildEntryIntelligenceShadow(a);if(ei)line+="\\n   ↳ Quality: "+ei.quality.grade+" ("+ei.quality.score+"/100)"+(ei.promotion.allowed===false?" • ⚠️ "+ei.promotion.reasons.join(","):"")+" • Fresh: "+ei.quote.freshness;L.push(line);});'
    new2='const ei=buildEntryIntelligenceShadow(a);if(ei)line+="\\n   ↳ Quality: "+ei.quality.grade+" ("+ei.quality.score+"/100)"+(ei.promotion.allowed===false?" • ⚠️ "+ei.promotion.reasons.join(","):"")+" • Fresh: "+ei.quote.freshness;line+="\\n   ↳ Why now: "+whyNowVi(a);L.push(line);});'
    assert s.count(old2)==1
    s=s.replace(old2,new2,1)
else:
    raise SystemExit('phase must be 028 or 030')

p.write_text(s)
