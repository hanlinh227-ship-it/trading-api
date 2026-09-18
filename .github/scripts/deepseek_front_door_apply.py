#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path, PurePosixPath

ALLOWED_FILES={
    "cloudflare-worker/validate-universal-canary.mjs",
    "cloudflare-worker/test-universal-canary.mjs",
}
TRUNC={"length","max_tokens"}
FENCE=chr(96)*3

def fail(reason):
    print("DEEPSEEK_PAYLOAD_VALID=FAIL")
    print("DEEPSEEK_OUTPUT_REJECTED="+reason,file=sys.stderr)
    raise SystemExit(1)

def main(argv):
    if len(argv)!=3: fail("usage")
    try:
        doc=json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except Exception: fail("response_invalid")
    choices=doc.get("choices") if isinstance(doc,dict) else None
    if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict): fail("choices_invalid")
    choice=choices[0]
    finish=choice.get("finish_reason")
    finish=finish if isinstance(finish,str) else "unknown"
    usage=doc.get("usage") if isinstance(doc.get("usage"),dict) else {}
    pt=usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"),int) else 0
    ct=usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"),int) else 0
    print("DEEPSEEK_FINISH_REASON="+(finish if finish in {"stop","length","max_tokens"} else "other"))
    print(f"DEEPSEEK_USAGE_PROMPT_TOKENS={pt}")
    print(f"DEEPSEEK_USAGE_COMPLETION_TOKENS={ct}")
    print(f"DEEPSEEK_SPEND_ESTIMATE_USD_LE={pt/1_000_000+ct*2/1_000_000:.6f}")
    msg=choice.get("message")
    content=msg.get("content") if isinstance(msg,dict) else None
    if not isinstance(content,str) or not content.strip(): fail("content_empty")
    s=content.strip()
    if s.startswith(FENCE):
        nl=s.find("\n")
        if nl<0 or not s.endswith(FENCE): fail("fence_invalid")
        s=s[nl+1:-3].strip()
    try: payload=json.loads(s)
    except Exception: fail("content_truncated" if finish in TRUNC else "payload_invalid")
    if not isinstance(payload,dict) or set(payload)!={"files"} or not isinstance(payload["files"],dict): fail("payload_shape")
    files=payload["files"]
    if set(files)!=ALLOWED_FILES: fail("file_set_mismatch")
    for rel,data in files.items():
        p=PurePosixPath(rel)
        if p.is_absolute() or ".." in p.parts or not isinstance(data,str): fail("file_invalid")
    root=Path(argv[2]).resolve()
    for rel,data in sorted(files.items()):
        target=root.joinpath(*PurePosixPath(rel).parts)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(data,encoding="utf-8")
        print("DEEPSEEK_FILE_WRITTEN="+rel)
    print("DEEPSEEK_PAYLOAD_VALID=PASS")
    print("DEEPSEEK_OUTPUT_APPLIED=PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv))
