#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 4:
    raise SystemExit('usage: meme_alpha_patch_v377.py SAFE_SIGNAL EXECUTOR SIGNER')
EXP, EXE, SIG = map(Path, sys.argv[1:4])


def sub1(text, pattern, repl, label, flags=0):
    out, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 replacement, got {count}')
    return out


def patch_signal(text):
    if "insiderRiskModel:'OBJECTIVE_ONCHAIN_CONCENTRATION_V1'" in text:
        return text
    text = sub1(text, r"const VERSION='[^']+';", "const VERSION='3.77.0-objective-insider-risk';", 'signal-version')
    anchor = "  const holderDecision=c.holderClusterAudit?.decision||c.holderClusterDecision||null;\n"
    if anchor not in text:
        raise RuntimeError('signal-holder-anchor')
    block = """  const holderMaxAccounts=num(c.holderClusterAudit?.maxAccountsSameOwner,c.holderClusterMaxAccountsSameOwner??999);
  const holderTopPct=finite(c.topHoldersPct)?Number(c.topHoldersPct):null;
  const whaleTop10Pct=finite(intel.whaleRow?.top10Pct)?Number(intel.whaleRow.top10Pct):null;
  const whaleDeltaTop10Pct=finite(intel.whaleRow?.deltaTop10Pct)?Number(intel.whaleRow.deltaTop10Pct):null;
  const insiderRiskReasons=[];
  let insiderRiskDecision='PASS';
  const insiderReview=r=>{insiderRiskReasons.push(r);if(insiderRiskDecision!=='BLOCK')insiderRiskDecision='REVIEW'};
  const insiderBlock=r=>{insiderRiskReasons.push(r);insiderRiskDecision='BLOCK'};
  if(holderDecision==='BLOCK')insiderBlock('HOLDER_CLUSTER_BLOCK');else if(holderDecision!=='PASS')insiderReview('HOLDER_CLUSTER_NOT_PASS');
  if(holderTopPct===null)insiderReview('TOP_HOLDERS_UNKNOWN');else if(holderTopPct>50)insiderBlock('TOP_HOLDERS_OVER_50');else if(holderTopPct>35)insiderReview('TOP_HOLDERS_OVER_35');
  if(holderMaxAccounts>=5)insiderBlock('SEVERE_MULTI_ACCOUNT_OWNER_CLUSTER');else if(holderMaxAccounts>=3)insiderReview('MULTI_ACCOUNT_OWNER_CLUSTER');
  if(whaleTop10Pct!==null&&whaleTop10Pct>=70&&whaleTop10Pct<100)insiderBlock('WHALE_TOP10_CONCENTRATION');
  if(whaleDeltaTop10Pct!==null&&whaleDeltaTop10Pct>=8)insiderBlock('WHALE_CONCENTRATION_SPIKE');
"""
    text = text.replace(anchor, anchor + block, 1)
    promotion = "    decision='PROBE_CANDIDATE';effectiveConsecutive=Math.max(1,effectiveConsecutive);entryGuardReasons.push(`V376_ROUTED_${router.selectedLane}`);\n  }\n"
    if promotion not in text:
        raise RuntimeError('signal-promotion-anchor')
    text = text.replace(promotion, promotion + "  if(insiderRiskDecision!=='PASS'&&decision==='PROBE_CANDIDATE'){decision='INSIDER_RISK_BLOCK';entryGuardReasons.push(`V377_INSIDER_${insiderRiskDecision}`);}\n", 1)
    old_return = "    securityDecision,holderClusterDecision:holderDecision,devIdentityProven:c.holderClusterAudit?.devIdentityProven===true,holderClusterMaxAccountsSameOwner:num(c.holderClusterAudit?.maxAccountsSameOwner),"
    new_return = "    securityDecision,holderClusterDecision:holderDecision,insiderRiskDecision,insiderRiskReasons:[...new Set(insiderRiskReasons)],insiderRiskModel:'OBJECTIVE_ONCHAIN_CONCENTRATION_V1',devIdentityStatus:c.holderClusterAudit?.devIdentityProven===true?'PROVEN':'UNATTRIBUTED',devIdentityProven:c.holderClusterAudit?.devIdentityProven===true,holderClusterMaxAccountsSameOwner:holderMaxAccounts,"
    if old_return not in text:
        raise RuntimeError('signal-return-anchor')
    text = text.replace(old_return, new_return, 1)
    text = sub1(text, r"  const common=\{decision:'WATCH'.*?freezeAuthorityDisabled:true\};", "  const common={decision:'WATCH',universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',holderClusterAudit:{decision:'PASS',maxAccountsSameOwner:1,devIdentityProven:false},topHoldersPct:20,sellRoute:true,sellPriceImpactPct:.4,token2022:false,mintAuthorityDisabled:true,freezeAuthorityDisabled:true};", 'signal-selftest-common')
    review = "  if(review.decision==='PROBE_CANDIDATE')throw new Error('SECURITY_REVIEW_PROMOTION_SELFTEST');\n"
    if review not in text:
        raise RuntimeError('signal-selftest-review')
    text = text.replace(review, review + "  const insider=guardCandidate({...common,mint:'I',score:85,liquidityUsd:700000,netBuyers5m:20,priceChange5m:2,buyVolume5m:300,sellVolume5m:100,holderClusterAudit:{decision:'REVIEW',maxAccountsSameOwner:3,devIdentityProven:false}},rt,wh,regime);\n  if(insider.decision==='PROBE_CANDIDATE'||insider.insiderRiskDecision==='PASS')throw new Error('INSIDER_RISK_PROMOTION_SELFTEST');\n", 1)
    text = text.replace("  console.log('HOLDER_PASS_REQUIRED=TRUE');\n", "  console.log('HOLDER_PASS_REQUIRED=TRUE');\n  console.log('OBJECTIVE_INSIDER_RISK_PASS_REQUIRED=TRUE');\n  console.log('DEV_IDENTITY_UNKNOWN_IS_NOT_MISREPRESENTED=TRUE');\n", 1)
    return text


def patch_executor(text):
    if 'function insiderSafe(c)' in text:
        return text
    impact = "function impact(c){return Math.abs(n(c?.sellPriceImpactPct??c?.sellImpactPct??c?.priceImpactPct,99))}\n"
    if impact not in text:
        raise RuntimeError('executor-impact-anchor')
    helper = "function insiderSafe(c){if(!c||c.insiderRiskDecision!=='PASS')return false;const top=Number(c.topHoldersPct),cluster=Number(c.holderClusterMaxAccountsSameOwner);if(!Number.isFinite(top)||top>35||!Number.isFinite(cluster)||cluster>2)return false;const wt=c.whaleTop10Pct,wd=c.whaleDeltaTop10Pct;if(wt!==null&&wt!==undefined&&wt!==''&&Number.isFinite(Number(wt))&&Number(wt)>=70&&Number(wt)<100)return false;if(wd!==null&&wd!==undefined&&wd!==''&&Number.isFinite(Number(wd))&&Number(wd)>=8)return false;return true}\n"
    text = text.replace(impact, impact + helper, 1)
    text = sub1(text, r"function coreSafe\(c\)\{return !!c&&c\.universeClass==='MEME_CONFIRMED'&&c\.securityDecision==='PASS'&&c\.holderClusterDecision==='PASS'&&", "function coreSafe(c){return !!c&&c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&insiderSafe(c)&&", 'executor-core-safe')
    text = sub1(text, r"  const c=\{mint:'C'.*?organicRatio5m:\.3\};", "  const c={mint:'C',universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',insiderRiskDecision:'PASS',topHoldersPct:20,holderClusterMaxAccountsSameOwner:1,whaleTop10Pct:25,whaleDeltaTop10Pct:0,decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:84,liquidityUsd:600000,sellPriceImpactPct:.3,consecutiveEligible:5,priceChange5m:2.5,netBuyers5m:20,avgNetBuyersLast2:15,scoreSlopeLast2:0,liquidityStableLast2:true,organicRatio5m:.3};", 'executor-selftest-c')
    text = sub1(text, r"  if\(!trendEntryEligible\(c\)\|\|trendEntryEligible\(\{\.\.\.c,priceChange5m:25\}\).*?throw new Error\('ENTRY_SAFETY_SELFTEST'\);", "  if(!trendEntryEligible(c)||trendEntryEligible({...c,priceChange5m:25})||trendEntryEligible({...c,securityDecision:'REVIEW'})||trendEntryEligible({...c,sellRoute:false})||trendEntryEligible({...c,token2022:true})||trendEntryEligible({...c,insiderRiskDecision:'REVIEW'})||trendEntryEligible({...c,topHoldersPct:40})||trendEntryEligible({...c,holderClusterMaxAccountsSameOwner:3}))throw new Error('ENTRY_SAFETY_SELFTEST');", 'executor-selftest-entry')
    text = text.replace("  console.log('MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS');", "  console.log('MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS');console.log('OBJECTIVE_INSIDER_RISK_DEFENSE_IN_DEPTH=TRUE');", 1)
    return text


def patch_signer(text):
    if 'def objective_insider_ok(c):' in text:
        return text
    marker = 'def candidate_ok(mint_out,p):\n'
    if marker not in text:
        raise RuntimeError('signer-candidate-anchor')
    helper = """def objective_insider_ok(c):
 try:
  top=float(c.get('topHoldersPct'));cluster=int(c.get('holderClusterMaxAccountsSameOwner'))
 except:return False
 if c.get('insiderRiskDecision')!='PASS' or top>35 or cluster>2:return False
 wt=c.get('whaleTop10Pct');wd=c.get('whaleDeltaTop10Pct')
 try:
  if wt is not None and 70<=float(wt)<100:return False
 except:return False
 try:
  if wd is not None and float(wd)>=8:return False
 except:return False
 return True
"""
    text = text.replace(marker, helper + marker, 1)
    text = sub1(text, r"^  hard=c\.get\('universeClass'\)==.*$", "  hard=c.get('universeClass')=='MEME_CONFIRMED' and c.get('securityDecision')=='PASS' and c.get('holderClusterDecision')=='PASS' and objective_insider_ok(c) and c.get('decision')=='PROBE_CANDIDATE' and not c.get('token2022') and c.get('sellRoute') is True and hard_empty(c.get('hardReject')) and liq>=50000 and impact<=float(p['maxBuyPriceImpactPct'])", 'signer-hard', re.M)
    text = text.replace("'version':'7.0'", "'version':'8.0'", 1)
    text = text.replace("'buyPolicy':'FAST_TREND_9_10_HARD_SAFETY_STAGED_CAPITAL'", "'buyPolicy':'FAST_TREND_OBJECTIVE_INSIDER_HARD_SAFETY_STAGED_CAPITAL'", 1)
    text = text.replace('meme-alpha-signer-v7', 'meme-alpha-signer-v8')
    text = text.replace('READY_SIGNER_V7_SELF_TEST', 'READY_SIGNER_V8_SELF_TEST')
    return text

for p in (EXP, EXE, SIG):
    if not p.is_file():
        raise RuntimeError(f'missing: {p}')
EXP.write_text(patch_signal(EXP.read_text()))
EXE.write_text(patch_executor(EXE.read_text()))
SIG.write_text(patch_signer(SIG.read_text()))
print('MEME_ALPHA_V377_PATCH_OK')
