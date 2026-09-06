from pathlib import Path
import re
import sys

p = Path(sys.argv[1])
s = p.read_text()

if 'V384_ADAPTIVE_OPPORTUNITY_QUEUE' not in s and 'V385_SEQUENTIAL_CLUSTER_SCAN' not in s:
    pat = r"const baseDeep = preliminary\.slice\(0,\s*\d+\);[^\n]*\nconst baseMints = new Set\(baseDeep\.map\(x => x\.result\?\.mint\)\);"
    rep = """// V384_ADAPTIVE_OPPORTUNITY_QUEUE
const V384_TOP_PRIORITY = Math.min(24, preliminary.length);
const V384_ROTATING_BUDGET = Math.min(40, Math.max(0, preliminary.length - V384_TOP_PRIORITY));
const V384_TAIL = preliminary.slice(V384_TOP_PRIORITY);
const V384_BUCKET = Math.max(1, V384_TAIL.length);
const V384_OFFSET = V384_TAIL.length ? Math.floor(Date.now() / 30000) % V384_BUCKET : 0;
const V384_ROTATED = V384_TAIL.length ? [...V384_TAIL.slice(V384_OFFSET), ...V384_TAIL.slice(0, V384_OFFSET)] : [];
const baseDeep = [...preliminary.slice(0, V384_TOP_PRIORITY), ...V384_ROTATED.slice(0, V384_ROTATING_BUDGET)];
const baseMints = new Set(baseDeep.map(x => x.result?.mint));"""
    s, n = re.subn(pat, rep, s, count=1)
    if n != 1:
        raise SystemExit('PATCH_MISMATCH_BASE_DEEP')
    s = re.sub(r"const extraMeme = preliminary\n\s*\.slice\(\d+\)",
               "const extraMeme = preliminary\n  .slice(V384_TOP_PRIORITY)", s, count=1)
    s = re.sub(r"\n\s*\.slice\(0,\s*\d+\);\nconst deep = \[\.\.\.baseDeep, \.\.\.extraMeme\];",
               "\n  .slice(0, 16);\nconst deep = [...baseDeep, ...extraMeme.filter(x=>!baseMints.has(x.result?.mint))];",
               s, count=1)

if 'V385_SEQUENTIAL_CLUSTER_SCAN' not in s:
    s, n = re.subn(r"const MAX_SELLABILITY_CHECKS_V216=\d+;[^\n]*",
                   "const MAX_SELLABILITY_CHECKS_V216=8; // V385_SEQUENTIAL_CLUSTER_SCAN: bounded expensive checks per cluster",
                   s, count=1)
    if n != 1:
        raise SystemExit('PATCH_MISMATCH_SELLABILITY')

    pat = r"// V384_ADAPTIVE_OPPORTUNITY_QUEUE.*?const baseMints = new Set\(baseDeep\.map\(x => x\.result\?\.mint\)\);"
    rep = """// V385_SEQUENTIAL_CLUSTER_SCAN
// One bounded group is deep-checked per cycle. Eight top candidates remain visible,
// while the rest of the preliminary universe is traversed cluster-by-cluster.
const V385_PRIORITY_RESERVE = Math.min(8, preliminary.length);
const V385_CLUSTER_SIZE = Math.min(36, Math.max(0, preliminary.length - V385_PRIORITY_RESERVE));
const V385_TAIL = preliminary.slice(V385_PRIORITY_RESERVE);
const V385_BUCKET_COUNT = Math.max(1, Math.ceil(V385_TAIL.length / Math.max(1, V385_CLUSTER_SIZE)));
const V385_BUCKET_INDEX = V385_TAIL.length ? Math.floor(Date.now() / 30000) % V385_BUCKET_COUNT : 0;
const V385_START = V385_BUCKET_INDEX * V385_CLUSTER_SIZE;
const V385_CLUSTER = V385_TAIL.slice(V385_START, V385_START + V385_CLUSTER_SIZE);
const baseDeep = [...preliminary.slice(0, V385_PRIORITY_RESERVE), ...V385_CLUSTER];
const baseMints = new Set(baseDeep.map(x => x.result?.mint));"""
    s, n = re.subn(pat, rep, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit('PATCH_MISMATCH_V384_BLOCK')

    s = re.sub(r"const extraMeme = preliminary\n\s*\.slice\([^\n]+\)",
               "const extraMeme = V385_CLUSTER", s, count=1)
    s = re.sub(r"\n\s*\.slice\(0,\s*16\);\nconst deep = \[\.\.\.baseDeep, \.\.\.extraMeme\.filter\(x=>!baseMints\.has\(x\.result\?\.mint\)\)\];",
               "\n  .slice(0, 8);\nconst deep = [...baseDeep, ...extraMeme.filter(x=>!baseMints.has(x.result?.mint))];",
               s, count=1)

p.write_text(s)
