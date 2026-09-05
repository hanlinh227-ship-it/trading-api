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
 p={'maxBuyLamports':20_000_000,'dailyBuyLamports':50_000_000,'maxOrdersPerHour':5,'maxPriceImpactPct':1.5,'jupiterBaseUrl':'https://api.jup.ag'}
 try:p.update(json.load(open(POLICY)))
 except FileNotFoundError:pass
 return p
def root_file(path,value):
 try:s=os.stat(path);return s.st_uid==0 and (s.st_mode&0o777)==0o640 and open(path).read().strip()==value
 except:return False
def ledger():
 try:return json.load(open(LEDGER))
 except:return {'orders':[]}
def save(x):
 t=LEDGER+'.tmp';open(t,'w').write(json.dumps(x,separators=(',',':')));os.chmod(t,0o600);os.replace(t,LEDGER)
def enforce(p,buy):
 now=time.time();l=ledger();day=[x for x in l.get('orders',[]) if now-float(x.get('ts',0))<86400];hour=[x for x in day if now-float(x.get('ts',0))<3600]
 if len(hour)>=int(p['maxOrdersPerHour']):raise PermissionError('HOURLY_ORDER_LIMIT')
 if sum(int(x.get('buyLamports',0)) for x in day)+buy>int(p['dailyBuyLamports']):raise PermissionError('DAILY_BUY_LIMIT')
 return l,day
def record(l,day,buy,rid):day.append({'ts':time.time(),'buyLamports':buy,'requestId':rid});l['orders']=day;save(l)
def mint(v):
 if not isinstance(v,str) or len(b58d(v))!=32:raise ValueError('MINT')
 return v
def get(url):
 q=urllib.request.Request(url,headers={'accept':'application/json','user-agent':'meme-alpha-signer-v3'});
 with urllib.request.urlopen(q,timeout=10) as r:return json.loads(r.read())
def order(r,seed,pkey,address,p):
 if not root_file(ENABLE,'ARMED=YES'):raise PermissionError('SIGNING_LOCKED')
 a,b=mint(r.get('inputMint')),mint(r.get('outputMint'))
 if (a==WSOL)==(b==WSOL):raise PermissionError('EXACTLY_ONE_WSOL')
 amount=int(str(r.get('amount',0)))
 if amount<=0:raise ValueError('AMOUNT')
 buy=amount if a==WSOL else 0
 if buy>int(p['maxBuyLamports']):raise PermissionError('BUY_SIZE_LIMIT')
 l,day=enforce(p,buy);maximp=min(float(r.get('maxPriceImpactPct',p['maxPriceImpactPct'])),float(p['maxPriceImpactPct']));qs=urllib.parse.urlencode({'inputMint':a,'outputMint':b,'amount':str(amount),'taker':address});j=get(str(p['jupiterBaseUrl']).rstrip('/')+'/swap/v2/order?'+qs);imp=float(j.get('priceImpactPct',0) or 0)
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
 if op=='health':return reply(c,{'ok':True,'service':'meme-alpha-signer','version':'3.0','mode':'READY' if seed else 'LOCKED','walletLoaded':bool(seed),'signingEnabled':bool(seed and root_file(ENABLE,'ARMED=YES')),'publicKey':address,'arbitraryRawSign':False})
 if op=='publicKey':return reply(c,{'ok':bool(seed),'publicKey':address,'error':None if seed else 'NO_WALLET'})
 if op=='order':
  if not seed:return reply(c,{'ok':False,'error':'NO_WALLET'})
  try:return reply(c,order(r,seed,pkey,address,p))
  except PermissionError as e:return reply(c,{'ok':False,'error':str(e)})
  except Exception as e:return reply(c,{'ok':False,'error':'ORDER_REJECTED_'+type(e).__name__})
 return reply(c,{'ok':False,'error':'UNSUPPORTED_OPERATION'})
def selftest():
 seed=os.urandom(32);p=pub(seed);msg=bytes([1,0,0,1])+p+b'\0'*32+bytes([0]);tx=bytes([1])+b'\0'*64+msg;s=sign_tx(tx,seed,p);assert s[1:65]!=b'\0'*64;assert b58d(b58e(p))==p;print('READY_SIGNER_V3_SELF_TEST=PASS');print('RAW_TRANSACTION_SIGNING=PASS');print('ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED');print('PERSISTENT_SPEND_LIMITER=IMPLEMENTED')
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
