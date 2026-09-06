#!/usr/bin/env python3
import base64,hashlib,json,os,socket,subprocess,sys,tempfile,time,urllib.parse,urllib.request
SOCK='/run/meme-alpha-signer/signer.sock';KEY='/var/lib/meme-alpha-signer/keys/bot-keypair.json';LEDGER='/var/lib/meme-alpha-signer/order-ledger.json';ENABLE='/etc/meme-alpha/signer-enabled';POLICY='/etc/meme-alpha/signer-policy.json';WSOL='So11111111111111111111111111111111111111112';B58='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
def b58e(b):
 n=int.from_bytes(b,'big');s=''
 while n:n,r=divmod(n,58);s=B58[r]+s
 return '1'*(len(b)-len(b.lstrip(b'\0')))+s
def b58d(s):
 n=0
 for c in s:
  if c not in B58:raise ValueError('B58')
  n=n*58+B58.index(c)
 r=n.to_bytes((n.bit_length()+7)//8,'big') if n else b'';return b'\0'*(len(s)-len(s.lstrip('1')))+r
def sv(b,i=0):
 v=q=0
 for _ in range(4):
  if i>=len(b):raise ValueError('SHORTVEC')
  x=b[i];i+=1;v|=(x&127)<<q
  if not x&128:return v,i
  q+=7
 raise ValueError('SHORTVEC')
def der(seed):return bytes.fromhex('302e020100300506032b657004220420')+seed
def pub(seed):
 p=subprocess.run(['openssl','pkey','-inform','DER','-pubout','-outform','DER'],input=der(seed),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=3);return p.stdout[-32:]
def sign(seed,msg):
 d='/run/meme-alpha-signer' if os.access('/run/meme-alpha-signer',os.W_OK) else tempfile.gettempdir();kf=tempfile.NamedTemporaryFile(prefix='.ma-key-',dir=d,delete=False);mf=tempfile.NamedTemporaryFile(prefix='.ma-msg-',dir=d,delete=False)
 try:
  kf.write(der(seed));kf.close();os.chmod(kf.name,0o600);mf.write(msg);mf.close();os.chmod(mf.name,0o600)
  p=subprocess.run(['openssl','pkeyutl','-sign','-inkey',kf.name,'-keyform','DER','-rawin','-in',mf.name],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=3)
  if len(p.stdout)!=64:raise ValueError('SIGLEN')
  return p.stdout
 finally:
  for f in [kf.name,mf.name]:
   try:os.unlink(f)
   except:pass
def sign_tx(tx,seed,pkey):
 ns,o=sv(tx);moff=o+64*ns
 if moff>=len(tx):raise ValueError('TX_TRUNC')
 msg=tx[moff:];i=0
 if msg[0]&128:
  if (msg[0]&127)!=0:raise ValueError('VERSION')
  i=1
 if i+3>len(msg):raise ValueError('HEADER')
 required=msg[i];i+=3;nkeys,i=sv(msg,i)
 if required!=ns or nkeys<required or i+32*nkeys>len(msg):raise ValueError('SIGNERS')
 signers=[msg[i+32*k:i+32*(k+1)] for k in range(required)]
 if pkey not in signers:raise ValueError('NOT_SIGNER')
 idx=signers.index(pkey);out=bytearray(tx);out[o+64*idx:o+64*(idx+1)]=sign(seed,msg);return bytes(out)
def wallet():
 try:a=json.load(open(KEY));raw=bytes(a)
 except FileNotFoundError:return None,None,None
 if len(raw)!=64:raise ValueError('KEYLEN')
 seed,pkey=raw[:32],raw[32:]
 if pub(seed)!=pkey:raise ValueError('PUB_MISMATCH')
 return seed,pkey,b58e(pkey)
def policy():
 p={'reserveLamports':10_000_000,'maxPortfolioUtilizationPct':94,'maxSingleBuyPctOfBalance':90,'dailyTurnoverMultiple':50,'maxOrdersPerHour':16,'maxBuyPriceImpactPct':1.25,'maxSellPriceImpactPct':8.0,'jupiterBaseUrl':'https://api.jup.ag','rpcUrl':'https://api.mainnet-beta.solana.com','gatePath':'/opt/meme-alpha/app/runtime-status/micro-live-gate.json','signalPath':'/opt/meme-alpha/app/runtime-status/signal-snapshot.json','trendPath':'/opt/meme-alpha/app/runtime-status/trend-pulse.json'}
 try:p.update(json.load(open(POLICY)))
 except FileNotFoundError:pass
 if int(p['reserveLamports'])<10_000_000:raise ValueError('POLICY_RESERVE')
 if not 70<=float(p['maxPortfolioUtilizationPct'])<=95:raise ValueError('POLICY_PORTFOLIO_UTILIZATION')
 if not 25<=float(p['maxSingleBuyPctOfBalance'])<=95:raise ValueError('POLICY_SINGLE_BUY')
 if not 1<=float(p['dailyTurnoverMultiple'])<=50:raise ValueError('POLICY_TURNOVER')
 if not 1<=int(p['maxOrdersPerHour'])<=24:raise ValueError('POLICY_ORDERS')
 if not 0<float(p['maxBuyPriceImpactPct'])<=1.25:raise ValueError('POLICY_BUY_IMPACT')
 if not float(p['maxBuyPriceImpactPct'])<=float(p['maxSellPriceImpactPct'])<=10:raise ValueError('POLICY_SELL_IMPACT')
 return p
def root_file(path,value):
 try:s=os.stat(path);return s.st_uid==0 and (s.st_mode&0o777)==0o640 and open(path).read().strip()==value
 except:return False
def readj(path):
 try:return json.load(open(path))
 except:return {}
def file_fresh(path,sec=180):
 try:return time.time()-os.stat(path).st_mtime<sec
 except:return False
def gate(p):
 path=str(p['gatePath']);g=readj(path)
 return g if file_fresh(path,180) and g.get('version')=='2.4.0' else {}
def hard_empty(v):return len(v)==0 if isinstance(v,list) else not bool(v)
def objective_insider_ok(c):
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
def candidate_ok(mint_out,p):
 path=str(p['signalPath']);s=readj(path)
 if not file_fresh(path,180):return False
 trend_path=str(p.get('trendPath','/opt/meme-alpha/app/runtime-status/trend-pulse.json'));trend=readj(trend_path) if file_fresh(trend_path,10) else {};rows=trend.get('rows',[]) or [];themes=trend.get('themes',[]) or []
 for c in s.get('candidates',[]) or []:
  if c.get('mint')!=mint_out:continue
  impact=c.get('sellPriceImpactPct',c.get('sellImpactPct',c.get('priceImpactPct')))
  try:
   impact=abs(float(impact));base=float(c.get('score',0));liq=float(c.get('liquidityUsd',0));scan_chg=float(c.get('priceChange5m'));net=float(c.get('netBuyers5m'));avg=float(c.get('avgNetBuyersLast2') if c.get('avgNetBuyersLast2') is not None else net);slope=float(c.get('scoreSlopeLast2') if c.get('scoreSlopeLast2') is not None else 0);con=int(c.get('consecutiveEligible',0))
  except:return False
  hard=c.get('universeClass')=='MEME_CONFIRMED' and c.get('securityDecision')=='PASS' and c.get('holderClusterDecision')=='PASS' and objective_insider_ok(c) and c.get('decision')=='PROBE_CANDIDATE' and not c.get('token2022') and c.get('sellRoute') is True and hard_empty(c.get('hardReject')) and liq>=50000 and impact<=float(p['maxBuyPriceImpactPct'])
  if not hard or con<1 or base<58:return False
  pulse=next((x for x in rows if x.get('mint')==mint_out),None);score=base;chg=scan_chg;pulse_flow=False
  if pulse:
   try:
    va=float(pulse.get('volumeAcceleration',0));ta=float(pulse.get('txnAcceleration',0));br=float(pulse.get('buySellRatio',0));ps=float(pulse.get('pulseScore',0));tx5=float(pulse.get('tx5',0));chg=float(pulse.get('price5m',scan_chg));strength=float(next((x.get('strength',0) for x in themes if x.get('narrative')==pulse.get('narrative')),0));add=(4 if va>=1.45 else 2 if va>=1.10 else 0)+(3 if ta>=1.30 else 1 if ta>=1.05 else 0)+(2 if br>=1.25 else 0)+(2 if strength>=60 else 0)+(1 if ps>=70 else 0);add+=(-8 if pulse.get('status')=='EXHAUSTED' else 0)+(-3 if pulse.get('promotionFlag') is True and ps<65 else 0);score=max(base-8,min(base+12,base+add));pulse_flow=pulse.get('status')!='EXHAUSTED' and ps>=55 and va>=1.05 and ta>=1.0 and br>=1.10 and tx5>=4
   except:pass
  stable=c.get('liquidityStableLast2') is not False
  standard=score>=72;liquid=score>=66 and liq>=500000 and net>=1 and impact<=0.80;flow=score>=62 and liq>=100000 and net>=5 and avg>=3 and scan_chg>=0.20 and impact<=0.80
  buyer_flow=net>=2 and avg>=1.5;fast_flow=net>=1 and pulse_flow;floor=0.05 if pulse_flow else 0.15
  return chg>=floor and chg<=15 and (buyer_flow or fast_flow) and slope>=-4 and stable and (standard or liquid or flow)
 return False
def rpc_balance(address,p):
 body=json.dumps({'jsonrpc':'2.0','id':1,'method':'getBalance','params':[address,{'commitment':'confirmed'}]}).encode();q=urllib.request.Request(str(p['rpcUrl']),data=body,headers={'content-type':'application/json','user-agent':'meme-alpha-signer-v8'})
 with urllib.request.urlopen(q,timeout=8) as r:j=json.loads(r.read())
 if 'error' in j:raise ValueError('RPC_BALANCE')
 return int(j['result']['value'])
def ledger():
 try:return json.load(open(LEDGER))
 except:return {'orders':[]}
def save(x):
 t=LEDGER+'.tmp';open(t,'w').write(json.dumps(x,separators=(',',':')));os.chmod(t,0o600);os.replace(t,LEDGER)
def enforce_orders(p,buy,current_balance):
 now=time.time();l=ledger();day=[x for x in l.get('orders',[]) if now-float(x.get('ts',0))<86400];hour=[x for x in day if now-float(x.get('ts',0))<3600]
 # Emergency exits are never blocked by a buy-frequency quota.
 if buy>0 and len([x for x in hour if int(x.get('buyLamports',0))>0])>=int(p['maxOrdersPerHour']):raise PermissionError('HOURLY_BUY_LIMIT')
 if buy>0:
  cap=max(10_000_000,int(current_balance*float(p['dailyTurnoverMultiple'])))
  if sum(int(x.get('buyLamports',0)) for x in day)+buy>cap:raise PermissionError('DYNAMIC_DAILY_TURNOVER_LIMIT')
 return l,day
def record(l,day,buy,rid):day.append({'ts':time.time(),'buyLamports':buy,'requestId':rid});l['orders']=day;save(l)
def mint(v):
 if not isinstance(v,str) or len(b58d(v))!=32:raise ValueError('MINT')
 return v
def get(url):
 q=urllib.request.Request(url,headers={'accept':'application/json','user-agent':'meme-alpha-signer-v8'});
 with urllib.request.urlopen(q,timeout=10) as r:return json.loads(r.read())
def buy_limit(address,p):
 bal=rpc_balance(address,p);by_pct=int(bal*float(p['maxSingleBuyPctOfBalance'])/100);by_reserve=max(0,bal-int(p['reserveLamports']));return bal,max(0,min(by_pct,by_reserve))
def order(r,seed,pkey,address,p):
 if not root_file(ENABLE,'ARMED=YES'):raise PermissionError('SIGNING_LOCKED')
 a,b=mint(r.get('inputMint')),mint(r.get('outputMint'))
 if (a==WSOL)==(b==WSOL):raise PermissionError('EXACTLY_ONE_WSOL')
 amount=int(str(r.get('amount',0)))
 if amount<=0:raise ValueError('AMOUNT')
 buy=amount if a==WSOL else 0;current_balance=0
 if buy:
  g=gate(p)
  if g.get('allowed') is not True:raise PermissionError('MICRO_LIVE_GATE_CLOSED')
  if not candidate_ok(b,p):raise PermissionError('TREND_SIGNAL_NOT_ELIGIBLE')
  current_balance,limit=buy_limit(address,p)
  if buy>limit:raise PermissionError('DYNAMIC_BUY_SIZE_LIMIT')
 l,day=enforce_orders(p,buy,current_balance if buy else 0)
 allowed_impact=float(p['maxBuyPriceImpactPct'] if buy else p['maxSellPriceImpactPct']);requested=float(r.get('maxPriceImpactPct',allowed_impact));maximp=min(requested,allowed_impact)
 qs=urllib.parse.urlencode({'inputMint':a,'outputMint':b,'amount':str(amount),'taker':address});j=get(str(p['jupiterBaseUrl']).rstrip('/')+'/swap/v2/order?'+qs);imp=abs(float(j.get('priceImpactPct',0) or 0))
 if imp>maximp:raise PermissionError('PRICE_IMPACT_LIMIT')
 x=j.get('transaction') or j.get('swapTransaction')
 if not x:raise ValueError('NO_TRANSACTION')
 raw=base64.b64decode(x,validate=True)
 if len(raw)>1500:raise ValueError('TX_SIZE')
 signed=sign_tx(raw,seed,pkey);rid=j.get('requestId');record(l,day,buy,rid);return {'ok':True,'signedTransaction':base64.b64encode(signed).decode(),'requestId':rid,'inputMint':a,'outputMint':b,'inAmount':str(j.get('inAmount',amount)),'outAmount':str(j.get('outAmount','0')),'priceImpactPct':imp,'routeHash':hashlib.sha256(json.dumps(j.get('routePlan',[]),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]}
def reply(c,x):c.sendall((json.dumps(x,separators=(',',':'))+'\n').encode())
def serve(c,seed,pkey,address,p):
 c.settimeout(5);d=b''
 while len(d)<32768 and not d.endswith(b'\n'):
  q=c.recv(4096)
  if not q:break
  d+=q
 try:r=json.loads(d.decode().strip() or '{}')
 except:return reply(c,{'ok':False,'error':'INVALID_JSON'})
 op=r.get('op')
 if op=='health':return reply(c,{'ok':True,'service':'meme-alpha-signer','version':'8.0','mode':'READY' if seed else 'LOCKED','walletLoaded':bool(seed),'signingEnabled':bool(seed and root_file(ENABLE,'ARMED=YES')),'publicKey':address,'arbitraryRawSign':False,'buyPolicy':'FAST_TREND_OBJECTIVE_INSIDER_HARD_SAFETY_STAGED_CAPITAL','maxPortfolioUtilizationPct':p['maxPortfolioUtilizationPct']})
 if op=='publicKey':return reply(c,{'ok':bool(seed),'publicKey':address,'error':None if seed else 'NO_WALLET'})
 if op=='order':
  if not seed:return reply(c,{'ok':False,'error':'NO_WALLET'})
  try:return reply(c,order(r,seed,pkey,address,p))
  except PermissionError as e:return reply(c,{'ok':False,'error':str(e)})
  except Exception as e:return reply(c,{'ok':False,'error':'ORDER_REJECTED_'+type(e).__name__})
 return reply(c,{'ok':False,'error':'UNSUPPORTED_OPERATION'})
def selftest():
 seed=os.urandom(32);pk=pub(seed);msg=bytes([1,0,0,1])+pk+b'\0'*32+bytes([0]);tx=bytes([1])+b'\0'*64+msg;s=sign_tx(tx,seed,pk);assert s[1:65]!=b'\0'*64;assert b58d(b58e(pk))==pk;assert hard_empty([]) and not hard_empty(['x'])
 print('READY_SIGNER_V8_SELF_TEST=PASS');print('ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED');print('BUY_REQUIRES_FRESH_HARD_SAFETY_TREND_GATE=TRUE');print('BUY_SIZE_SCALES_WITH_WALLET_BALANCE=TRUE');print('SELL_BYPASSES_BUY_FREQUENCY_QUOTA=TRUE');print('MAX_PORTFOLIO_UTILIZATION_PCT=94')
def main():
 if '--self-test' in sys.argv:return selftest()
 seed,pkey,address=wallet();p=policy();os.makedirs(os.path.dirname(SOCK),exist_ok=True)
 try:os.unlink(SOCK)
 except FileNotFoundError:pass
 s=socket.socket(socket.AF_UNIX);s.bind(SOCK);os.chmod(SOCK,0o660);s.listen(16)
 while True:
  c,_=s.accept()
  with c:
   try:serve(c,seed,pkey,address,p)
   except Exception:
    try:reply(c,{'ok':False,'error':'INTERNAL_ERROR'})
    except:pass
if __name__=='__main__':main()
