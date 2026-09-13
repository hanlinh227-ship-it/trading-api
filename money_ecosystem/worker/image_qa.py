from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

@dataclass(frozen=True)
class AssetQAResult:
    accepted:bool; sha256:str|None; identity_status:str; reason:str|None

def validate_image(path,expected_width,expected_height,seen_hashes=None,identity_evidence=None):
    p=Path(path)
    if not p.is_file() or p.stat().st_size==0: return AssetQAResult(False,None,"UNVERIFIED","missing/empty image")
    digest=sha256(p.read_bytes()).hexdigest()
    if seen_hashes is not None and digest in seen_hashes: return AssetQAResult(False,digest,"UNVERIFIED","duplicate image")
    try:
        from PIL import Image
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            if im.size != (expected_width,expected_height): return AssetQAResult(False,digest,"UNVERIFIED",f"wrong dimensions: {im.size}")
    except Exception as e: return AssetQAResult(False,digest,"UNVERIFIED",f"decode failed: {e}")
    status="UNVERIFIED"
    if identity_evidence is not None:
        status="VERIFIED" if identity_evidence is True else "HEURISTIC"
    if seen_hashes is not None: seen_hashes.add(digest)
    return AssetQAResult(True,digest,status,None)
