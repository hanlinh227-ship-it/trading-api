// Virtual tranche ledger for BTCUSDT one-way mode.
// Bybit exposes one net BTCUSDT position; this ledger preserves strategy-level entry/risk provenance.

const n=v=>Number.isFinite(Number(v))?Number(v):0;

export function newTranche({id,side,qty,entry,initialSl,setupType,regime,riskUsd,createdAt=Date.now()}={}){
  return {id:String(id||createdAt),side:String(side||""),qty:Math.abs(n(qty)),entry:n(entry),initialSl:n(initialSl),managedSl:n(initialSl),setupType:String(setupType||""),regime:String(regime||""),riskUsd:Math.max(0,n(riskUsd)),createdAt,status:"OPEN",peakR:0,currentR:0,protected:false};
}

export function effectiveRiskUsd(t){
  const q=Math.abs(n(t?.qty)),e=n(t?.entry),s=n(t?.managedSl),side=String(t?.side||"");
  if(!(q>0&&e>0&&s>0))return Math.max(0,n(t?.riskUsd));
  if(side==="Buy"&&s>=e)return 0;
  if(side==="Sell"&&s<=e)return 0;
  return Math.abs(e-s)*q;
}

export function activeRiskUsd(ledger=[]){
  return ledger.filter(t=>t?.status==="OPEN").reduce((sum,t)=>sum+effectiveRiskUsd(t),0);
}

export function markProtected(t,managedSl){
  const out={...t,managedSl:n(managedSl)};
  out.protected=out.side==="Buy"?out.managedSl>=out.entry:out.side==="Sell"?out.managedSl<=out.entry:false;
  return out;
}

export function reconcileLedgerToNetPosition(ledger=[],netQty=0){
  const open=ledger.filter(t=>t?.status==="OPEN"),ledgerQty=open.reduce((s,t)=>s+Math.abs(n(t.qty)),0),target=Math.abs(n(netQty));
  return {ok:Math.abs(ledgerQty-target)<=1e-9,ledgerQty,targetQty:target,openCount:open.length};
}
