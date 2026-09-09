from pathlib import Path

# V3.14 pipeline trigger: root Wrangler config is now available for dry-run/deploy.
P=Path('scripts/patch_signalhub_v314_simple_stability.py')
s=P.read_text()

helper='''\ndef between(text,start,end,repl,label):\n    i=text.find(start)\n    if i<0:\n        raise SystemExit(f'{label}: start marker missing')\n    j=text.find(end,i)\n    if j<0:\n        raise SystemExit(f'{label}: end marker missing')\n    return text[:i]+repl+text[j:]\n'''
if 'def between(text,start,end,repl,label):' not in s:
    anchor="def sub1(text, pattern, repl, label):\n    out,n=re.subn(pattern,repl,text,count=1,flags=re.S)\n    if n!=1:\n        raise SystemExit(f'{label}: expected 1 replacement, got {n}')\n    return out\n"
    if anchor not in s: raise SystemExit('sub1 helper anchor missing')
    s=s.replace(anchor,anchor+helper,1)

def convert(label,start_marker,end_marker,strip_suffix=''):
    global s
    token=f"''','{label}')"
    end=s.find(token)
    if end<0:
        print(label,'already converted or missing');return
    call=s.rfind('a=sub1(a,',0,end)
    if call<0: raise SystemExit(f'{label}: call missing')
    triple=s.find("r'''",call,end)
    if triple<0: raise SystemExit(f'{label}: replacement triple missing')
    body=s[triple+4:end]
    if strip_suffix and body.rstrip().endswith(strip_suffix):
        body=body.rstrip()[:-len(strip_suffix)].rstrip()+"\n"
    new=f'a=between(a,{start_marker!r},{end_marker!r},r\'\'\'{body}\'\'\',\'{label}\')'
    s=s[:call]+new+s[end+len(token):]
    print('converted',label)

# One-line Java methods confuse regexes that expect a closing brace on its own line.
# Convert them to deterministic start/end marker replacements before the main patch runs.
convert('performance summary','    private String performanceSummary(){','    private View signalCard(JSONObject s){')
convert('signal card','    private View signalCard(JSONObject s){','    private TextView metric(','    private TextView metric')
convert('signals screen','    private void renderSignals(boolean animate){','    private void addCryptoSignalGroup(','    private void addCryptoSignalGroup')

P.write_text(s)
print('normalized V3.14 patch')
