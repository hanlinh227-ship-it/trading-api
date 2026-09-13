from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

class ContractError(ValueError): pass

@dataclass(frozen=True)
class Reference:
    id: str
    path: Path
    character: str

@dataclass(frozen=True)
class Scene:
    id: int
    prompt: str
    reference_ids: Tuple[str, ...]

@dataclass(frozen=True)
class ImageRenderJob:
    project_id: str
    width: int
    height: int
    max_attempts: int
    workflow_profile: str
    references: Tuple[Reference, ...]
    scenes: Tuple[Scene, ...]

    @classmethod
    def from_payload(cls, payload, workspace_root):
        for k in ("project_id","width","height","references","scenes"):
            if k not in payload: raise ContractError(f"missing required field: {k}")
        w,h=int(payload["width"]),int(payload["height"])
        if w<=0 or h<=0 or w>1024 or h>576 or w%8 or h%8: raise ContractError("unsafe image dimensions")
        attempts=int(payload.get("max_attempts",2))
        if attempts<1 or attempts>4: raise ContractError("max_attempts must be 1..4")
        root=Path(workspace_root).resolve(); refs=[]; ids=set()
        for r in payload["references"]:
            rid=str(r.get("id","")).strip()
            if not rid or rid in ids: raise ContractError("duplicate/empty reference id")
            rel=Path(str(r.get("path","")))
            if rel.is_absolute() or ".." in rel.parts: raise ContractError("reference path escapes workspace")
            resolved=(root/rel).resolve()
            try: resolved.relative_to(root)
            except ValueError: raise ContractError("reference path escapes workspace")
            ids.add(rid); refs.append(Reference(rid,resolved,str(r.get("character",rid))))
        scenes=[]; scene_ids=set()
        for s in payload["scenes"]:
            sid=int(s.get("id",0)); prompt=str(s.get("prompt","")).strip(); used=tuple(s.get("reference_ids",()))
            if sid<=0 or sid in scene_ids or not prompt: raise ContractError("invalid scene")
            if any(x not in ids for x in used): raise ContractError("scene uses undeclared reference")
            scene_ids.add(sid); scenes.append(Scene(sid,prompt,used))
        if not refs or not scenes: raise ContractError("references/scenes cannot be empty")
        return cls(str(payload["project_id"]),w,h,attempts,str(payload.get("workflow_profile","sd15_reference_lowvram")),tuple(refs),tuple(scenes))
