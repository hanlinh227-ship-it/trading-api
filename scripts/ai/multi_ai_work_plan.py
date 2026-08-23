#!/usr/bin/env python3
"""Deterministic conflict-free work planner for the five-provider gateway."""
from __future__ import annotations
import json,sys
from pathlib import PurePosixPath
PROVIDERS=("deepseek","qwen","codex","claude","openrouter")
ROLE={"deepseek":"PRIMARY_REPAIR","qwen":"PARALLEL_REPAIR_TEST","codex":"TECHNICAL_SECURITY_REVIEW","claude":"ARCHITECTURE_REGRESSION_REVIEW","openrouter":"ADVERSARIAL_FALLBACK"}

def norm_path(value:str)->str:
    raw=value.strip()
    if not raw or "\\" in raw:
        raise ValueError(f"unsafe allowed path: {value!r}")
    original=PurePosixPath(raw)
    if original.is_absolute() or any(part in ("..","") for part in original.parts):
        raise ValueError(f"unsafe allowed path: {value!r}")
    p=str(original)
    if p in (".","") or p.startswith("/"):
        raise ValueError(f"unsafe allowed path: {value!r}")
    return p

def plan(task:dict)->dict:
    task_id=str(task.get("task_id") or "").strip();base_sha=str(task.get("base_sha") or "").strip();objective=str(task.get("objective") or "").strip()
    if not task_id or len(base_sha)!=40 or not all(c in "0123456789abcdefABCDEF" for c in base_sha):raise ValueError("task_id and 40-hex base_sha are required")
    if not objective:raise ValueError("objective is required")
    raw_paths=task.get("allowed_paths") or []
    if not isinstance(raw_paths,list) or not raw_paths:raise ValueError("allowed_paths must be a non-empty list")
    paths=sorted(dict.fromkeys(norm_path(str(x)) for x in raw_paths))
    # Repository safety policy is stricter than path-disjoint parallel writes:
    # exactly one source writer is active for a task. The other four providers
    # stay fully parallel as read-only test/review/proposal lanes.
    lanes=[
      {"provider":"deepseek","role":ROLE["deepseek"],"mode":"WRITE","paths":paths},
      {"provider":"qwen","role":ROLE["qwen"],"mode":"READ_ONLY_TEST","paths":paths},
      {"provider":"codex","role":ROLE["codex"],"mode":"READ_ONLY","paths":paths},
      {"provider":"claude","role":ROLE["claude"],"mode":"READ_ONLY","paths":paths},
      {"provider":"openrouter","role":ROLE["openrouter"],"mode":"READ_ONLY","paths":paths},
    ]
    writers=[x for x in lanes if x["mode"]=="WRITE"]
    if len(writers)!=1 or writers[0]["provider"]!="deepseek":
        raise RuntimeError("planner must emit exactly one source writer")
    return {"task_id":task_id,"base_sha":base_sha.lower(),"objective":objective,"dispatch_mode":"PARALLEL_SINGLE_WRITER","lanes":lanes,"invariants":{"exact_head_required":True,"cas_before_push":True,"reviewers_are_read_only":True,"single_source_writer":True,"signal_v11_authority_changed":False}}

def main()->int:
    if len(sys.argv)>2:print("usage: multi_ai_work_plan.py [task.json]",file=sys.stderr);return 2
    data=json.load(open(sys.argv[1],encoding="utf-8")) if len(sys.argv)==2 else json.load(sys.stdin)
    print(json.dumps(plan(data),ensure_ascii=False,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
