#!/usr/bin/env python3
import csv, hashlib, json, math, random
from collections import Counter
from pathlib import Path

ROOT=Path('data/vietlott/power655')
ROWS=list(csv.DictReader((ROOT/'power655_all_draws.csv').open()))
D=[tuple(int(r[f'n{i}']) for i in range(1,7)) for r in ROWS]
IDS=[r['draw_id'] for r in ROWS]
N=len(D)
BASE=6/55

# Strict prequential protocol requested by user:
# know draws 1..10 -> predict 11; reveal 11 -> know 1..11 -> predict 12; repeat.
# SHA256 is tested as a deterministic feature/PRNG mixer, not assumed to reveal lottery RNG state.

def enc(history, window, salt, variant):
    h=history[-window:] if window else history
    if variant==0:
        s='|'.join(','.join(map(str,x)) for x in h)
    elif variant==1:
        s='|'.join('-'.join(f'{v:02d}' for v in sorted(x)) for x in h)
    elif variant==2:
        s='|'.join(str(sum(x)) for x in h)+'|'+','.join(map(str,h[-1]))
    else:
        s='|'.join(''.join(f'{v:02d}' for v in x) for x in h)
    return f'{salt}|{variant}|{window}|{s}'.encode()

def sha_pick(history, rule):
    window,salt,variant,rounds,offset,stride,mix=rule
    digest=hashlib.sha256(enc(history,window,salt,variant)).digest()
    for j in range(rounds-1): digest=hashlib.sha256(digest+str(j).encode()).digest()
    stream=bytearray(digest)
    while len(stream)<256: stream.extend(hashlib.sha256(bytes(stream[-32:])).digest())
    vals=[]; p=offset%len(stream)
    guard=0
    while len(vals)<6 and guard<1000:
        z=int.from_bytes(bytes([stream[p%len(stream)],stream[(p+1)%len(stream)]]),'big')
        if mix==1: z ^= sum(history[-1])*257
        elif mix==2: z += sum(sum(x) for x in history[-min(7,len(history)):])
        elif mix==3: z ^= int.from_bytes(digest[-2:],'big')
        x=(z%55)+1
        if x not in vals: vals.append(x)
        p=(p+stride)%len(stream); guard+=1
    if len(vals)<6:
        for x in range(1,56):
            if x not in vals: vals.append(x)
            if len(vals)==6: break
    return tuple(sorted(vals))

def score_rule(rule,start,end):
    hist=[0]*7; matches=0
    for t in range(start,end):
        pred=set(sha_pick(D[:t],rule)); k=len(pred & set(D[t])); hist[k]+=1; matches+=k
    n=end-start
    return {'draws':n,'histogram':hist,'matches':matches,'mean_hits':matches/n,'number_accuracy':matches/(6*n),
            'lift_vs_random':matches/(6*n)-BASE,'rate_3plus':sum(hist[3:])/n,'rate_4plus':sum(hist[4:])/n,
            'rate_5plus':sum(hist[5:])/n,'rate_6':hist[6]/n}

def rule_dict(r):
    return dict(zip(['window','salt','variant','rounds','offset','stride','mix'],r))

# Keep final 240 draws out of formula search. Discovery begins with exactly 10 known draws.
DEV_END=max(10,N-240)
RNG=random.Random(655256)
windows=[1,2,3,5,7,10,14,21,34,55,89,144,233,0]
# 30k deterministic SHA256 structures: broad enough for GitHub Actions, reproducible.
rules=[]
for i in range(30000):
    rules.append((RNG.choice(windows),f's{i}_{RNG.randrange(1<<30)}',RNG.randrange(4),RNG.randrange(1,5),RNG.randrange(32),RNG.choice([1,3,5,7,11,13,17,19,23,29,31]),RNG.randrange(4)))

# Stage A cheap discovery on spaced development targets, all predictions strictly use only prior draws.
probe_targets=list(range(10,DEV_END,5))
def probe(rule):
    m=0
    for t in probe_targets: m+=len(set(sha_pick(D[:t],rule)) & set(D[t]))
    return m/(6*len(probe_targets))
ranked=sorted(((probe(r),r) for r in rules),reverse=True)[:120]

# Stage B full sequential development for finalists; select before holdout.
full=[]
for _,r in ranked:
    s=score_rule(r,10,DEV_END); full.append((s['number_accuracy'],s,r))
full.sort(key=lambda x:x[0],reverse=True)
best_acc,best_dev,best_rule=full[0]
hold=score_rule(best_rule,DEV_END,N)

# Also record first 20 true blind sequential predictions for auditability.
audit=[]
for t in range(10,min(N,30)):
    p=sha_pick(D[:t],best_rule); audit.append({'target_draw_id':IDS[t],'known_through':IDS[t-1],'prediction':p,'actual':D[t],'hits':len(set(p)&set(D[t]))})

out={
 'draw_count':N,
 'protocol':'prequential: know 1..10 predict 11, reveal 11, know 1..11 predict 12, repeat; no future draw enters a prediction',
 'sha256_role':'deterministic hash feature/PRNG mixer; no claim that SHA256 can invert or expose Vietlott RNG state',
 'random_number_accuracy':BASE,
 'search':{'generated_rules':len(rules),'probe_step':5,'probe_finalists':len(ranked),'development_start_index_1based':11,'development_end_draw_id':IDS[DEV_END-1],'holdout_draws':N-DEV_END},
 'selected_rule':rule_dict(best_rule),
 'development':best_dev,
 'holdout':hold,
 'achieved_80pct_number_accuracy':hold['number_accuracy']>=0.80,
 'top10_development':[{'rule':rule_dict(r),'development':s} for _,s,r in full[:10]],
 'early_audit':audit,
 'warning':'Rule search is selected on development only. Holdout is reported without tuning. SHA256 outputs should be random-like absent access to the lottery RNG seed/state; high development scores can be selection noise.'
}
(ROOT/'sha256_prequential_research.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'selected_rule':out['selected_rule'],'development_accuracy':best_dev['number_accuracy'],'holdout_accuracy':hold['number_accuracy'],'holdout_histogram':hold['histogram'],'achieved_80pct':out['achieved_80pct_number_accuracy']},indent=2))
