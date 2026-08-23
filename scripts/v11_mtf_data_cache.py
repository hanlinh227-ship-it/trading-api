#!/usr/bin/env python3
# V11 MTF exact historical data cache (research only).
# Owner directive 2026-08-24: restore the proven legacy data routes; Yahoo is forbidden.
from __future__ import annotations
import hashlib,json,lzma,math,os,re,struct,time,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
CATALOG_PATH=ROOT/'cloudflare-worker/v11/symbol-catalog.js'
DEFAULT_CACHE_DIR=ROOT/'data/v11_mtf_cache'
CACHE_VERSION='V11-MTF-CACHE-V2-LEGACY-NO-YAHOO'
USER_AGENT='trading-api-v11-legacy-data/3.0'
CACHE_TF={'forex':'m5','crypto':'h4','metal':'h1','index':'h1'}
DUKAS_INSTRUMENT={'XAUUSD':'XAUUSD','XAGUSD':'XAGUSD','NAS100':'USATECHIDXUSD','US30':'USA30IDXUSD','US500':'USA500IDXUSD','DEX':'DEUIDXEUR','JP225':'JPNIDXJPY'}
DUKAS_BOUNDS={k:((10.0,100000.0) if k=='XAUUSD' else (0.1,10000.0) if k=='XAGUSD' else (100.0,1000000.0)) for k in DUKAS_INSTRUMENT}

def safe_float(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except Exception:return None

def load_catalog():
    text=CATALOG_PATH.read_text(encoding='utf-8');cats={}
    for m in ('forex','crypto','metal','index'):
        z=re.search(rf'{m}:Object\.freeze\(\[(.*?)\]\)',text,re.S)
        if not z:raise RuntimeError('catalog parse '+m)
        cats[m]=re.findall(r"'([^']+)'",z.group(1))
    if sum(map(len,cats.values()))!=95:raise RuntimeError('catalog count')
    return cats

def market_for_symbol(symbol):
    s=re.sub(r'[^A-Z0-9]','',str(symbol).upper())
    for m,rows in load_catalog().items():
        if s in rows:return m
    return None

def get_json(url,timeout=45,retries=4,headers=None):
    last=None
    for n in range(retries):
        try:
            h={'User-Agent':USER_AGENT,'Accept':'application/json'};h.update(headers or {})
            with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=timeout) as r:return json.loads(r.read().decode('utf-8'))
        except Exception as e:last=e;time.sleep(.45*(n+1))
    raise RuntimeError('HTTP_FAIL '+str(last))

def rawget(url,timeout=40,retries=3):
    last=None
    for n in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/octet-stream,*/*'}),timeout=timeout) as r:return r.read()
        except HTTPError as e:
            if e.code==404:return b''
            last=e
        except Exception as e:last=e
        time.sleep(.45*(n+1))
    raise RuntimeError('HTTP_FAIL '+str(last))

def _td_key():
    k=os.environ.get('TWELVEDATA_API_KEY','').strip()
    if not k:raise RuntimeError('TWELVEDATA_API_KEY_MISSING')
    return k

def _td_obj(data,expected):
    if isinstance(data,dict) and 'meta' in data and 'values' in data:return data
    if isinstance(data,dict):
        for k,v in data.items():
            if isinstance(v,dict) and str((v.get('meta') or {}).get('symbol','')).upper()==expected.upper():return v
    return None

def twelvedata_forex_m5(symbol,start_ts,end_ts):
    s=re.sub(r'[^A-Z]','',str(symbol).upper());pair=s[:3]+'/'+s[3:];out=[];end_dt=datetime.fromtimestamp(end_ts,timezone.utc);guard=0
    while guard<32:
        guard+=1
        params={'symbol':pair,'interval':'5min','outputsize':5000,'timezone':'UTC','order':'ASC','end_date':end_dt.strftime('%Y-%m-%d %H:%M:%S')}
        url='https://api.twelvedata.com/time_series?'+urllib.parse.urlencode(params)
        j=get_json(url,90,3,{'Authorization':'apikey '+_td_key()});obj=_td_obj(j,pair)
        if not obj:raise RuntimeError('TWELVEDATA_BAD_RESPONSE '+str(j)[:180])
        meta=obj.get('meta') or {}
        if str(meta.get('symbol','')).upper()!=pair:raise RuntimeError('TWELVEDATA_META_MISMATCH')
        vals=obj.get('values') or []
        if not vals:break
        page=[]
        for x in vals:
            dt=datetime.fromisoformat(str(x['datetime']).replace('Z','+00:00'))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            t=int(dt.timestamp());row=[t,float(x['open']),float(x['high']),float(x['low']),float(x['close']),float(x.get('volume') or 0)]
            page.append(row)
            if start_ts<=t<=end_ts:out.append(row)
        oldest=min(r[0] for r in page)
        if oldest<=start_ts:break
        end_dt=datetime.fromtimestamp(oldest-300,timezone.utc)
        time.sleep(.08)
    d={r[0]:r for r in out}
    if not d:raise RuntimeError('TWELVEDATA_M5_EMPTY')
    return [d[k] for k in sorted(d)],'Twelve Data Forex M5',True,'FOREX:'+s

def _base(symbol):
    s=re.sub(r'[^A-Z0-9]','',str(symbol).upper())
    if not s.endswith('USDT'):raise RuntimeError('CRYPTO_NOT_USDT '+s)
    return s[:-4]

def kucoin_4h(symbol,start_ts,end_ts):
    inst=_base(symbol)+'-USDT';out=[];cur=start_ts;span=1450*14400
    while cur<=end_ts:
        z=min(end_ts,cur+span);q=urllib.parse.urlencode({'type':'4hour','symbol':inst,'startAt':cur,'endAt':z});j=get_json('https://api.kucoin.com/api/v1/market/candles?'+q)
        if str(j.get('code'))!='200000':raise RuntimeError(str(j.get('msg') or j)[:180])
        for x in j.get('data') or []:
            if len(x)>=6:out.append([int(x[0]),float(x[1]),float(x[3]),float(x[4]),float(x[2]),float(x[5])])
        cur=z+1;time.sleep(.02)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d:raise RuntimeError('KUCOIN_EMPTY')
    return [d[k] for k in sorted(d)],'KuCoin Spot 4H',True,'SPOT:'+re.sub(r'[^A-Z0-9]','',symbol.upper())

def gate_4h(symbol,start_ts,end_ts):
    pair=_base(symbol)+'_USDT';out=[];cur=start_ts;span=950*14400
    while cur<=end_ts:
        z=min(end_ts,cur+span);q=urllib.parse.urlencode({'currency_pair':pair,'interval':'4h','from':cur,'to':z,'limit':'1000'});arr=get_json('https://api.gateio.ws/api/v4/spot/candlesticks?'+q)
        if isinstance(arr,dict):raise RuntimeError(str(arr.get('message') or arr)[:180])
        for x in arr or []:
            if len(x)>=6:out.append([int(float(x[0])),float(x[5]),float(x[3]),float(x[4]),float(x[2]),float(x[6]) if len(x)>6 else float(x[1] or 0)])
        cur=z+1;time.sleep(.02)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d:raise RuntimeError('GATE_EMPTY')
    return [d[k] for k in sorted(d)],'Gate.io Spot 4H',True,'SPOT:'+re.sub(r'[^A-Z0-9]','',symbol.upper())

def okx_4h(symbol,start_ts,end_ts):
    inst=_base(symbol)+'-USDT';out=[];after=None
    for _ in range(40):
        p={'instId':inst,'bar':'4H','limit':'100'}
        if after is not None:p['after']=str(after)
        j=get_json('https://www.okx.com/api/v5/market/history-candles?'+urllib.parse.urlencode(p));arr=j.get('data') or []
        if str(j.get('code'))!='0':raise RuntimeError(str(j.get('msg') or j)[:180])
        if not arr:break
        ts=[]
        for x in arr:
            t=int(x[0])//1000;ts.append(t);out.append([t,float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])])
        oldest=min(ts)
        if oldest<=start_ts:break
        nxt=oldest*1000
        if nxt==after:break
        after=nxt;time.sleep(.03)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d:raise RuntimeError('OKX_EMPTY')
    return [d[k] for k in sorted(d)],'OKX Spot 4H',True,'SPOT:'+re.sub(r'[^A-Z0-9]','',symbol.upper())

def mexc_4h(symbol,start_ts,end_ts):
    s=re.sub(r'[^A-Z0-9]','',symbol.upper());out=[];cur=start_ts*1000;end=end_ts*1000;span=950*14400*1000
    for _ in range(24):
        if cur>end:break
        z=min(end,cur+span);q=urllib.parse.urlencode({'symbol':s,'interval':'4h','startTime':cur,'endTime':z,'limit':1000});arr=get_json('https://api.mexc.com/api/v3/klines?'+q,30,3)
        if isinstance(arr,dict):raise RuntimeError(str(arr.get('msg') or arr)[:180])
        if not arr:break
        for x in arr:
            if len(x)>=6:out.append([int(x[0])//1000,float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])])
        nxt=int(arr[-1][0])+14400000
        if nxt<=cur:break
        cur=nxt;time.sleep(.03)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d:raise RuntimeError('MEXC_EMPTY')
    return [d[k] for k in sorted(d)],'MEXC Spot 4H',True,'SPOT:'+s

def _month_floor(dt):return datetime(dt.year,dt.month,1,tzinfo=timezone.utc)
def _next_month(dt):return (dt.replace(day=28)+timedelta(days=4)).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
def _decode_dukas_record(symbol,base_ts,rec):
    off,p1,p2,p3,p4,vol=rec;o=p1/1000.0;lo,hi=DUKAS_BOUNDS[symbol]
    for oo,hh,ll,cc in ((o,p4/1000.0,p3/1000.0,p2/1000.0),(o,p2/1000.0,p3/1000.0,p4/1000.0)):
        if all(math.isfinite(v) and lo<=v<=hi for v in (oo,hh,ll,cc)) and ll<=min(oo,cc)<=max(oo,cc)<=hh:return [int(base_ts+int(off)),oo,hh,ll,cc,float(vol) if math.isfinite(float(vol)) else 0.0]
    return None

def dukascopy_h1(symbol,start_ts,end_ts):
    s=re.sub(r'[^A-Z0-9]','',str(symbol).upper());inst=DUKAS_INSTRUMENT[s];cur=_month_floor(datetime.fromtimestamp(start_ts,timezone.utc));end_dt=datetime.fromtimestamp(end_ts,timezone.utc);out=[]
    while cur<=end_dt:
        blob=rawget(f'https://datafeed.dukascopy.com/datafeed/{inst}/{cur.year}/{cur.month-1:02d}/BID_candles_hour_1.bi5')
        if blob:
            raw=lzma.decompress(blob);usable=len(raw)-(len(raw)%24);base_ts=int(cur.timestamp())
            for rec in struct.iter_unpack('>IIIIIf',raw[:usable]):
                row=_decode_dukas_record(s,base_ts,rec)
                if row and start_ts<=row[0]<=end_ts:out.append(row)
        cur=_next_month(cur)
    d={r[0]:r for r in out};rows=[d[k] for k in sorted(d)]
    if not rows:raise RuntimeError('DUKAS_EMPTY')
    return rows,f'Dukascopy {inst} BID Spot/Index H1',True,('BID:'+inst)

def provider_spec(symbol,market):
    s=re.sub(r'[^A-Z0-9]','',str(symbol).upper())
    if market=='forex':return {'base_tf':'m5','provider':'twelvedata_forex_m5','instrument':'FOREX:'+s}
    if market=='crypto':return {'base_tf':'h4','provider':'legacy_exchange_spot_4h','instrument':'SPOT:'+s}
    if market in ('metal','index'):return {'base_tf':'h1','provider':'dukascopy_bid_h1','instrument':'BID:'+DUKAS_INSTRUMENT[s]}
    raise RuntimeError('unknown market '+market)

def fetch_raw(symbol,market,start_ts,end_ts):
    if market=='forex':
        rows,src,exact,inst=twelvedata_forex_m5(symbol,start_ts,end_ts);return rows,src,exact,inst,provider_spec(symbol,market)
    if market=='crypto':
        errors=[]
        for fn in (kucoin_4h,gate_4h,okx_4h,mexc_4h):
            try:
                rows,src,exact,inst=fn(symbol,start_ts,end_ts);return rows,src,exact,inst,provider_spec(symbol,market)
            except Exception as e:errors.append(fn.__name__+':'+str(e))
        raise RuntimeError('CRYPTO_LEGACY_ROUTES_FAIL '+' | '.join(errors)[:1200])
    rows,src,exact,inst=dukascopy_h1(symbol,start_ts,end_ts);return rows,src,exact,inst,provider_spec(symbol,market)

def compute_data_hash(rows):return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _req_key(symbol,market,instrument,provider,base_tf,start_ts,end_ts):return '|'.join([CACHE_VERSION,str(symbol).upper(),market,instrument,provider,base_tf,str(int(start_ts)),str(int(end_ts))])
def _req_key_with_hash(symbol,market,instrument,provider,base_tf,start_ts,end_ts,h):return _req_key(symbol,market,instrument,provider,base_tf,start_ts,end_ts)+'|content='+h
def _cache_path(cache_dir,key):return Path(cache_dir)/(hashlib.sha256(key.encode()).hexdigest()+'.json')
def load_cache(cache_dir,symbol,market,start_ts,end_ts):
    spec=provider_spec(symbol,market);key=_req_key(symbol,market,spec['instrument'],spec['provider'],spec['base_tf'],start_ts,end_ts);p=_cache_path(cache_dir,key)
    if not p.exists():return None,spec,key
    try:
        obj=json.loads(p.read_text());expected={'cacheVersion':CACHE_VERSION,'symbol':str(symbol).upper(),'market':market,'instrument':spec['instrument'],'provider':spec['provider'],'baseTimeframe':spec['base_tf'],'startTs':int(start_ts),'endTs':int(end_ts)}
        if any(obj.get(f)!=v for f,v in expected.items()):raise ValueError('CACHE_MISMATCH')
        rows=obj.get('rows');h=compute_data_hash(rows)
        if h!=obj.get('contentHash'):raise ValueError('CACHE_HASH')
        return {'rows':rows,'source':obj.get('source'),'exact':bool(obj.get('exact')),'instrument':spec['instrument'],'cached':True},spec,key
    except Exception:return None,spec,key

def save_cache(cache_dir,key,symbol,market,spec,rows,source,exact,start_ts,end_ts):
    h=compute_data_hash(rows);obj={'cacheVersion':CACHE_VERSION,'cacheKey':_req_key_with_hash(symbol,market,spec['instrument'],spec['provider'],spec['base_tf'],start_ts,end_ts,h),'symbol':str(symbol).upper(),'market':market,'instrument':spec['instrument'],'provider':spec['provider'],'baseTimeframe':spec['base_tf'],'startTs':int(start_ts),'endTs':int(end_ts),'source':source,'exact':bool(exact),'contentHash':h,'rows':rows};p=_cache_path(cache_dir,key);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,separators=(',',':')));os.replace(tmp,p)
def feature_schema_hash(schema):return hashlib.sha256(('V11-MTF-FEATURE-SCHEMA|'+schema).encode()).hexdigest()[:16]
def _feature_path(cache_dir,symbol,data_hash,schema_hash):return Path(cache_dir)/('feat_'+hashlib.sha256('|'.join([CACHE_VERSION,'FEAT',str(symbol).upper(),data_hash,schema_hash]).encode()).hexdigest()+'.json')
def load_feature(cache_dir,symbol,data_hash,schema_hash):
    p=_feature_path(cache_dir,symbol,data_hash,schema_hash)
    try:
        obj=json.loads(p.read_text());return obj.get('features') if obj.get('cacheVersion')==CACHE_VERSION and obj.get('symbol')==str(symbol).upper() and obj.get('dataHash')==data_hash and obj.get('schemaHash')==schema_hash else None
    except Exception:return None
def save_feature(cache_dir,symbol,data_hash,schema_hash,features):
    p=_feature_path(cache_dir,symbol,data_hash,schema_hash);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'cacheVersion':CACHE_VERSION,'symbol':str(symbol).upper(),'dataHash':data_hash,'schemaHash':schema_hash,'features':features},separators=(',',':')))
def parse_dt(v):
    if isinstance(v,(int,float)):return datetime.fromtimestamp(int(v),timezone.utc)
    d=datetime.fromisoformat(str(v).replace('Z','+00:00').replace(' ','T'));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
def main(argv=None):
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--symbol');ap.add_argument('--market');ap.add_argument('--start');ap.add_argument('--end');ap.add_argument('--days',type=int,default=400);ap.add_argument('--cache-dir',default=str(DEFAULT_CACHE_DIR));ap.add_argument('--force-refresh',action='store_true');args=ap.parse_args(argv)
    end=parse_dt(args.end) if args.end else datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0);start=parse_dt(args.start) if args.start else end-timedelta(days=args.days);start_ts,end_ts=int(start.timestamp()),int(end.timestamp());cache_dir=Path(args.cache_dir);cache_dir.mkdir(parents=True,exist_ok=True);cats=load_catalog();items=[(re.sub(r'[^A-Z0-9]','',args.symbol.upper()),args.market or market_for_symbol(args.symbol))] if args.symbol else [(s,m) for m in ('forex','crypto','metal','index') for s in cats[m]];counts={}
    for symbol,market in items:
        entry,spec,key=load_cache(cache_dir,symbol,market,start_ts,end_ts)
        if entry and not args.force_refresh:rows=entry['rows'];counts[symbol]=len(rows);print('CACHE_HIT',market,symbol,len(rows),entry['source'],flush=True)
        else:
            try:rows,source,exact,instrument,spec=fetch_raw(symbol,market,start_ts,end_ts);save_cache(cache_dir,key,symbol,market,spec,rows,source,exact,start_ts,end_ts);counts[symbol]=len(rows);print('FETCH_CACHE',market,symbol,len(rows),source,flush=True)
            except Exception as e:counts[symbol]=0;print('FETCH_FAIL',market,symbol,str(e)[:300],flush=True)
    print('SUMMARY',json.dumps({'fetched':sum(bool(v) for v in counts.values()),'failed':sum(not bool(v) for v in counts.values()),'total':len(items)},separators=(',',':')),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())