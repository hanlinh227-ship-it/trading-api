#!/usr/bin/env bash
set -euo pipefail

APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
SERVICE=meme-alpha-paper.service
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/var/lib/meme-alpha/data/backups/v100-jupiter-$STAMP

rollback() {
  rc=$?
  echo "ROLLBACK rc=$rc"
  if [ -f "$BACKUP/position.js" ]; then
    cp -f "$BACKUP/position.js" "$APP/src/position.js"
    chown meme-alpha:meme-alpha "$APP/src/position.js" || true
  fi
  systemctl start "$SERVICE" || true
  exit "$rc"
}
trap rollback ERR

cd "$APP"
mkdir -p "$BACKUP"
cp -a src/position.js "$BACKUP/position.js"

echo '=== V1.0 JUPITER PAPER DEPLOY ==='
node - <<'NODE'
const fs=require('fs');
const cfg=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(cfg.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
console.log('JUPITER='+cfg.jupiter);
NODE

echo '=== JUPITER BUY/SELL QUOTE PRETEST ==='
node - <<'NODE'
const fs=require('fs');
const cfg=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
const st=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/state.json','utf8'));
const pos=(st.openPositions||[])[0];
if(!pos?.mint) throw new Error('NO_OPEN_POSITION_FOR_QUOTE_TEST');
const WSOL='So11111111111111111111111111111111111111112';
async function rpcDecimals(mint){
  const r=await fetch(cfg.rpc,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'getAccountInfo',params:[mint,{encoding:'jsonParsed'}]}),signal:AbortSignal.timeout(10000)});
  if(!r.ok) throw new Error('RPC_HTTP_'+r.status);
  const j=await r.json();
  const d=Number(j?.result?.value?.data?.parsed?.info?.decimals);
  if(!Number.isInteger(d)||d<0||d>18) throw new Error('TOKEN_DECIMALS_UNAVAILABLE');
  return d;
}
async function order(inputMint,outputMint,amount){
  let last;
  for(let i=0;i<2;i++){
    try{
      const u=new URL(cfg.jupiter+'/swap/v2/order');
      u.searchParams.set('inputMint',inputMint);
      u.searchParams.set('outputMint',outputMint);
      u.searchParams.set('amount',String(amount));
      const r=await fetch(u,{headers:{accept:'application/json'},signal:AbortSignal.timeout(12000)});
      if(!r.ok) throw new Error('JUP_HTTP_'+r.status);
      const j=await r.json();
      if(!j?.outAmount || BigInt(j.outAmount)<=0n) throw new Error('JUP_NO_OUT_AMOUNT');
      return j;
    }catch(e){last=e;if(i===0) await new Promise(r=>setTimeout(r,1500));}
  }
  throw last;
}
const d=await rpcDecimals(pos.mint);
const buy=await order(WSOL,pos.mint,1000000n);
const qtyRaw=BigInt(Math.max(1,Math.floor(Number(pos.qty||0)*10**d*0.01)));
const sell=await order(pos.mint,WSOL,qtyRaw);
console.log('TEST_MINT='+pos.mint);
console.log('TOKEN_DECIMALS='+d);
console.log('BUY_OUT_RAW='+buy.outAmount);
console.log('BUY_IMPACT='+(buy.priceImpactPct ?? 'NA'));
console.log('SELL_OUT_LAMPORTS='+sell.outAmount);
console.log('SELL_IMPACT='+(sell.priceImpactPct ?? 'NA'));
console.log('JUPITER_QUOTE_PRETEST_PASS');
NODE

systemctl stop "$SERVICE"

python3 - <<'PY'
from pathlib import Path
import re
p=Path('/opt/meme-alpha/app/src/position.js')
s=p.read_text()

if 'JUPITER_SWAP_V2_ORDER' in s:
    print('ALREADY_PATCHED')
    raise SystemExit(0)

# Insert exact-size Jupiter quote helpers immediately after getJSON().
pat=r'''async function getJSON\(url\) \{.*?\n\}\n\nasync function bestDexPrice'''
m=re.search(pat,s,re.S)
if not m:
    raise SystemExit('HELPER_INSERT_TARGET_NOT_FOUND')
block=m.group(0)
helper=block[:-len('async function bestDexPrice')] + r'''async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(10000)
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

async function mintDecimals(mint) {
  const j = await postJSON(cfg.rpc, {
    jsonrpc: "2.0",
    id: 1,
    method: "getAccountInfo",
    params: [mint, { encoding: "jsonParsed" }]
  });
  const d = Number(j?.result?.value?.data?.parsed?.info?.decimals);
  if (!Number.isInteger(d) || d < 0 || d > 18) {
    throw new Error("TOKEN_DECIMALS_UNAVAILABLE");
  }
  return d;
}

function toRawAmount(amountUi, decimals) {
  const scaled = Math.floor(Number(amountUi) * 10 ** Number(decimals));
  if (!Number.isSafeInteger(scaled) || scaled <= 0) {
    throw new Error("RAW_AMOUNT_UNSAFE_OR_ZERO");
  }
  return BigInt(scaled);
}

async function jupiterExactIn(inputMint, outputMint, amountRaw) {
  const u = new URL(`${cfg.jupiter}/swap/v2/order`);
  u.searchParams.set("inputMint", inputMint);
  u.searchParams.set("outputMint", outputMint);
  u.searchParams.set("amount", amountRaw.toString());
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const r = await fetch(u, {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(12000)
      });
      if (!r.ok) throw new Error(`JUPITER_ORDER_HTTP_${r.status}`);
      const j = await r.json();
      if (!j?.outAmount || BigInt(j.outAmount) <= 0n) {
        throw new Error("JUPITER_ORDER_NO_OUT_AMOUNT");
      }
      return j;
    } catch (e) {
      lastError = e;
      if (attempt < 2) {
        await new Promise(resolve => setTimeout(resolve, 1500));
      }
    }
  }
  throw lastError || new Error("JUPITER_ORDER_FAILED");
}

async function bestDexPrice'''
s=s[:m.start()]+helper+s[m.end():]

old=r'''  const grossUsd =
    qty * market.priceUsd;

  const grossSol =
    grossUsd / solUsd;

  const costPct =
    executionCostPct(
      grossUsd,
      market.liquidityUsd
    );

  const netSol =
    grossSol *
    (1 - costPct);'''
new=r'''  const grossUsd =
    qty * market.priceUsd;

  const grossSol =
    grossUsd / solUsd;

  const tokenDecimals =
    Number.isInteger(Number(pos.tokenDecimals))
      ? Number(pos.tokenDecimals)
      : await mintDecimals(pos.mint);

  pos.tokenDecimals = tokenDecimals;

  const sellAmountRaw =
    toRawAmount(qty, tokenDecimals);

  const sellQuote =
    await jupiterExactIn(
      pos.mint,
      WSOL,
      sellAmountRaw
    );

  const netSol =
    Number(sellQuote.outAmount) / 1e9;

  if (!Number.isFinite(netSol) || netSol <= 0) {
    throw new Error("JUPITER_SELL_INVALID_OUTPUT");
  }

  const costPct =
    grossSol > 0
      ? Math.max(0, 1 - netSol / grossSol)
      : 0;'''
if old not in s:
    raise SystemExit('SELL_BLOCK_TARGET_NOT_FOUND')
s=s.replace(old,new,1)

old=r'''        const positionUsd =
          allocationSol *
          solUsd;

        const costPct =
          executionCostPct(
            positionUsd,
            market.liquidityUsd
          );

        const deploySol =
          allocationSol *
          (1 - costPct);

        const tokenQty =
          (
            deploySol *
            solUsd
          ) /
          market.priceUsd;

        const obs ='''
new=r'''        const tokenDecimals =
          Number.isInteger(Number(cand.decimals))
            ? Number(cand.decimals)
            : await mintDecimals(t.mint);

        const inputLamports =
          toRawAmount(allocationSol, 9);

        const buyQuote =
          await jupiterExactIn(
            WSOL,
            t.mint,
            inputLamports
          );

        const tokenQty =
          Number(buyQuote.outAmount) /
          10 ** tokenDecimals;

        if (!Number.isFinite(tokenQty) || tokenQty <= 0) {
          throw new Error("JUPITER_BUY_INVALID_OUTPUT");
        }

        const entryPriceUsd =
          (allocationSol * solUsd) /
          tokenQty;

        const deploySol =
          (tokenQty * market.priceUsd) /
          solUsd;

        const costPct =
          allocationSol > 0
            ? Math.max(0, 1 - deploySol / allocationSol)
            : 0;

        const obs ='''
if old not in s:
    raise SystemExit('BUY_BLOCK_TARGET_NOT_FOUND')
s=s.replace(old,new,1)

# Replace the two entry-price fields in the new-position / trade record section.
s=s.replace('''          entryPriceUsd:\n            market.priceUsd,''','''          entryPriceUsd:\n            entryPriceUsd,''',2)

needle='''          qty:\n            tokenQty,\n'''
repl='''          qty:\n            tokenQty,\n\n          tokenDecimals,\n'''
if needle not in s:
    raise SystemExit('TOKEN_DECIMALS_FIELD_TARGET_NOT_FOUND')
s=s.replace(needle,repl,1)

needle='''          simulatedEntryCostPct:\n            costPct * 100\n'''
repl='''          simulatedEntryCostPct:\n            costPct * 100,\n\n          executionModel:\n            "JUPITER_SWAP_V2_ORDER",\n\n          jupiterInputAmountRaw:\n            inputLamports.toString(),\n\n          jupiterOutputAmountRaw:\n            String(buyQuote.outAmount),\n\n          jupiterPriceImpactPct:\n            buyQuote.priceImpactPct ?? null\n'''
if needle not in s:
    raise SystemExit('POSITION_EXEC_FIELDS_TARGET_NOT_FOUND')
s=s.replace(needle,repl,1)

needle='''    simulatedExecutionCostPct:\n      costPct * 100\n'''
repl='''    simulatedExecutionCostPct:\n      costPct * 100,\n    executionModel:\n      "JUPITER_SWAP_V2_ORDER",\n    jupiterInputAmountRaw:\n      sellAmountRaw.toString(),\n    jupiterOutputAmountRaw:\n      String(sellQuote.outAmount),\n    jupiterPriceImpactPct:\n      sellQuote.priceImpactPct ?? null\n'''
if needle not in s:
    raise SystemExit('SELL_TRADE_FIELDS_TARGET_NOT_FOUND')
s=s.replace(needle,repl,1)

needle='''          simulatedExecutionCostPct:\n            costPct * 100\n'''
repl='''          simulatedExecutionCostPct:\n            costPct * 100,\n\n          executionModel:\n            "JUPITER_SWAP_V2_ORDER",\n\n          jupiterInputAmountRaw:\n            inputLamports.toString(),\n\n          jupiterOutputAmountRaw:\n            String(buyQuote.outAmount),\n\n          jupiterPriceImpactPct:\n            buyQuote.priceImpactPct ?? null\n'''
if needle not in s:
    raise SystemExit('BUY_TRADE_FIELDS_TARGET_NOT_FOUND')
s=s.replace(needle,repl,1)

s=s.replace('=== PAPER POSITION ENGINE v0.4 ===','=== PAPER POSITION ENGINE v1.0 JUPITER SIZE-SPECIFIC ===',1)

p.write_text(s)
print('V100_PATCH_APPLIED')
PY

chown meme-alpha:meme-alpha src/position.js
node --check src/position.js

echo '=== STATIC ASSERT ==='
grep -nE 'JUPITER_SWAP_V2_ORDER|jupiterExactIn|tokenDecimals|PAPER POSITION ENGINE v1.0' src/position.js

echo 'SYNTAX_PASS'
systemctl start "$SERVICE"
sleep 70

echo '=== SERVICE ==='
systemctl --no-pager is-active "$SERVICE"
systemctl --no-pager is-enabled "$SERVICE"

echo '=== RECENT POSITION LOG ==='
tail -80 /var/log/meme-alpha/paper.log | grep -E 'PAPER POSITION ENGINE|OPEN_PROBE|ENTRY_FAIL|PAPER_PROBE|POSITION_ENGINE_STATUS|CYCLE_COMPLETE|Equity=|Realized=|Unrealized=' || true

echo '=== SAFETY ASSERT ==='
node - <<'NODE'
const fs=require('fs');
const cfg=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
if(cfg.mode!=='PAPER') throw new Error('MODE_CHANGED_FROM_PAPER');
const src=fs.readFileSync('/opt/meme-alpha/app/src/position.js','utf8');
if(!src.includes('JUPITER_SWAP_V2_ORDER')) throw new Error('JUPITER_MODEL_MISSING');
if(src.includes('=== PAPER POSITION ENGINE v0.4 ===')) throw new Error('OLD_ENGINE_BANNER_PRESENT');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
console.log('V100_JUPITER_INVARIANT_PASS');
NODE

echo '=== RESOURCES ==='
free -h
uptime

echo "V100_JUPITER_DEPLOY_COMPLETE"
echo "BACKUP=$BACKUP"
trap - ERR
