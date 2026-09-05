#!/usr/bin/env python3
import base64, hashlib, json, os, socket, subprocess, sys, tempfile, urllib.parse, urllib.request

SOCKET_PATH='/run/meme-alpha-signer/signer.sock'
KEY_PATH='/var/lib/meme-alpha-signer/keys/bot-keypair.json'
ENABLE_PATH='/etc/meme-alpha/signer-enabled'
POLICY_PATH='/etc/meme-alpha/signer-policy.json'
WSOL='So11111111111111111111111111111111111111112'
B58='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def b58encode(raw: bytes) -> str:
    n=int.from_bytes(raw,'big'); out=''
    while n: n,r=divmod(n,58); out=B58[r]+out
    pad=0
    for b in raw:
        if b: break
        pad+=1
    return '1'*pad+(out or ('' if pad else '1'))


def b58decode(s: str) -> bytes:
    n=0
    for ch in s:
        if ch not in B58: raise ValueError('INVALID_BASE58')
        n=n*58+B58.index(ch)
    raw=n.to_bytes((n.bit_length()+7)//8,'big') if n else b''
    pad=len(s)-len(s.lstrip('1'))
    return b'\x00'*pad+raw


def read_shortvec(buf: bytes, off: int):
    value=0; shift=0; start=off
    while True:
        if off>=len(buf) or off-start>3: raise ValueError('SHORTVEC_INVALID')
        b=buf[off]; off+=1; value|=(b&0x7f)<<shift
        if not (b&0x80): return value,off
        shift+=7


def parse_message_signers(message: bytes):
    i=0
    if not message: raise ValueError('EMPTY_MESSAGE')
    if message[0]&0x80:
        version=message[0]&0x7f
        if version!=0: raise ValueError('UNSUPPORTED_MESSAGE_VERSION')
        i=1
    if i+3>len(message): raise ValueError('MESSAGE_HEADER_TRUNCATED')
    required=message[i]; i+=3
    count,i=read_shortvec(message,i)
    if count<required or i+32*count>len(message): raise ValueError('ACCOUNT_KEYS_TRUNCATED')
    keys=[message[i+32*k:i+32*(k+1)] for k in range(count)]
    return required,keys[:required]


def pkcs8_der_from_seed(seed: bytes) -> bytes:
    if len(seed)!=32: raise ValueError('SEED_LENGTH')
    return bytes.fromhex('302e020100300506032b657004220420')+seed


def openssl_pub_from_seed(seed: bytes) -> bytes:
    der=pkcs8_der_from_seed(seed)
    p=subprocess.run(['openssl','pkey','-inform','DER','-pubout','-outform','DER'],input=der,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    if len(p.stdout)<32: raise ValueError('OPENSSL_PUB_DER')
    return p.stdout[-32:]


def openssl_sign(seed: bytes, message: bytes) -> bytes:
    der=pkcs8_der_from_seed(seed)
    with tempfile.NamedTemporaryFile(prefix='meme-alpha-ed25519-',dir='/run/meme-alpha-signer',delete=False) as f:
        f.write(der); path=f.name
    os.chmod(path,0o600)
    try:
        p=subprocess.run(['openssl','pkeyutl','-sign','-inkey',path,'-keyform','DER','-rawin'],input=message,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=3)
        if len(p.stdout)!=64: raise ValueError('SIGNATURE_LENGTH')
        return p.stdout
    finally:
        try: os.unlink(path)
        except FileNotFoundError: pass


def sign_serialized_transaction(tx: bytes, seed: bytes, pub: bytes) -> bytes:
    sig_count,sig_start=read_shortvec(tx,0)
    msg_off=sig_start+64*sig_count
    if msg_off>=len(tx): raise ValueError('TRANSACTION_TRUNCATED')
    msg=tx[msg_off:]
    required,signers=parse_message_signers(msg)
    if sig_count!=required: raise ValueError('SIGNATURE_COUNT_MISMATCH')
    try: idx=signers.index(pub)
    except ValueError: raise ValueError('BOT_PUBKEY_NOT_REQUIRED_SIGNER')
    sig=openssl_sign(seed,msg)
    out=bytearray(tx); off=sig_start+64*idx; out[off:off+64]=sig
    return bytes(out)


def load_wallet():
    try:
        a=json.load(open(KEY_PATH,'r',encoding='utf-8'))
        raw=bytes(int(x) for x in a)
        if len(raw)!=64: raise ValueError('KEYPAIR_LENGTH')
        seed,pub=raw[:32],raw[32:]
        derived=openssl_pub_from_seed(seed)
        if derived!=pub: raise ValueError('KEYPAIR_PUBLIC_MISMATCH')
        return seed,pub,b58encode(pub)
    except FileNotFoundError:
        return None,None,None


def load_policy():
    d={'maxBuyLamports':20000000,'maxPriceImpactPct':1.5,'jupiterBaseUrl':'https://api.jup.ag'}
    try: d.update(json.load(open(POLICY_PATH,'r',encoding='utf-8')))
    except FileNotFoundError: pass
    return d


def is_enabled():
    try:
        st=os.stat(ENABLE_PATH)
        return st.st_uid==0 and (st.st_mode&0o777)==0o640 and open(ENABLE_PATH,'r',encoding='utf-8').read().strip()=='ARMED=YES'
    except Exception: return False


def http_json(url):
    req=urllib.request.Request(url,headers={'accept':'application/json','user-agent':'meme-alpha-signer/1.7'})
    with urllib.request.urlopen(req,timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))


def safe_mint(v):
    if not isinstance(v,str) or not (32<=len(v)<=50): raise ValueError('MINT_FORMAT')
    b=b58decode(v)
    if len(b)!=32: raise ValueError('MINT_LENGTH')
    return v


def create_signed_jupiter_order(req,seed,pub,address,policy):
    if not is_enabled(): raise PermissionError('SIGNING_LOCKED')
    inp=safe_mint(req.get('inputMint')); out=safe_mint(req.get('outputMint'))
    if (inp==WSOL)==(out==WSOL): raise PermissionError('POLICY_REQUIRES_EXACTLY_ONE_WSOL_SIDE')
    amount=int(str(req.get('amount','0')))
    if amount<=0: raise ValueError('AMOUNT_INVALID')
    if inp==WSOL and amount>int(policy['maxBuyLamports']): raise PermissionError('BUY_SIZE_POLICY_EXCEEDED')
    max_impact=min(float(req.get('maxPriceImpactPct',policy['maxPriceImpactPct'])),float(policy['maxPriceImpactPct']))
    q=urllib.parse.urlencode({'inputMint':inp,'outputMint':out,'amount':str(amount),'taker':address})
    body=http_json(str(policy['jupiterBaseUrl']).rstrip('/')+'/swap/v2/order?'+q)
    impact=float(body.get('priceImpactPct',0) or 0)
    if impact>max_impact: raise PermissionError('PRICE_IMPACT_POLICY_EXCEEDED')
    tx64=body.get('transaction') or body.get('swapTransaction')
    if not isinstance(tx64,str): raise ValueError('JUPITER_TRANSACTION_MISSING')
    raw=base64.b64decode(tx64,validate=True)
    if len(raw)>1500: raise ValueError('TRANSACTION_TOO_LARGE')
    signed=sign_serialized_transaction(raw,seed,pub)
    return {'ok':True,'signedTransaction':base64.b64encode(signed).decode(),'requestId':body.get('requestId'),'inputMint':inp,'outputMint':out,'inAmount':str(body.get('inAmount',amount)),'outAmount':str(body.get('outAmount','0')),'priceImpactPct':impact,'routePlanHash':hashlib.sha256(json.dumps(body.get('routePlan',[]),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]}


def reply(c,p): c.sendall((json.dumps(p,separators=(',',':'))+'\n').encode())


def handle(c,seed,pub,address,policy):
    c.settimeout(4); data=b''
    while len(data)<32768 and not data.endswith(b'\n'):
        x=c.recv(4096)
        if not x: break
        data+=x
    try: req=json.loads(data.decode().strip() or '{}')
    except Exception: return reply(c,{'ok':False,'error':'INVALID_JSON'})
    op=req.get('op')
    if op=='health':
        return reply(c,{'ok':True,'service':'meme-alpha-signer','mode':'READY' if seed else 'LOCKED','signingEnabled':bool(seed and is_enabled()),'walletLoaded':bool(seed),'publicKey':address,'liveExecution':False})
    if op=='publicKey': return reply(c,{'ok':bool(seed),'publicKey':address,'error':None if seed else 'NO_WALLET'})
    if op=='order':
        if not seed: return reply(c,{'ok':False,'error':'NO_WALLET'})
        try: return reply(c,create_signed_jupiter_order(req,seed,pub,address,policy))
        except PermissionError as e: return reply(c,{'ok':False,'error':str(e)})
        except Exception as e: return reply(c,{'ok':False,'error':f'ORDER_REJECTED_{type(e).__name__}'})
    return reply(c,{'ok':False,'error':'UNSUPPORTED_OPERATION'})


def self_test():
    seed=os.urandom(32); pub=openssl_pub_from_seed(seed); msg=bytes([1,0,0,1])+pub+b'\x00'*32+bytes([0]); tx=bytes([1])+b'\x00'*64+msg; signed=sign_serialized_transaction(tx,seed,pub); assert signed[1:65]!=b'\x00'*64
    assert b58decode(b58encode(pub))==pub
    print('READY_SIGNER_SELF_TEST=PASS'); print('RAW_TRANSACTION_SIGNING=PASS'); print('ARBITRARY_RAW_SIGN_OP=NOT_IMPLEMENTED')


def main():
    if '--self-test' in sys.argv: return self_test()
    seed,pub,address=load_wallet(); policy=load_policy(); os.makedirs(os.path.dirname(SOCKET_PATH),exist_ok=True)
    try: os.unlink(SOCKET_PATH)
    except FileNotFoundError: pass
    srv=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);srv.bind(SOCKET_PATH);os.chmod(SOCKET_PATH,0o660);srv.listen(16)
    print(f'SIGNER_MODE={"READY" if seed else "LOCKED"}',flush=True);print(f'WALLET_LOADED={str(bool(seed)).lower()}',flush=True);print(f'SIGNING_ENABLED={str(bool(seed and is_enabled())).lower()}',flush=True)
    while True:
        c,_=srv.accept()
        with c:
            try: handle(c,seed,pub,address,policy)
            except Exception as e:
                try: reply(c,{'ok':False,'error':'INTERNAL_ERROR'})
                except Exception: pass
                print(f'request_error={type(e).__name__}',file=sys.stderr,flush=True)

if __name__=='__main__': main()
