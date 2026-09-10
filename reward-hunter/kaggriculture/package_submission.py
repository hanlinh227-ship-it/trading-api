from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "dist" / "submission.tar.gz"))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    main_py = HERE / "main.py"
    champion = HERE / "champion.json"
    if not main_py.exists():
        raise SystemExit("missing main.py")
    if not champion.exists():
        champion.write_text(json.dumps({"schema": "KAGGRICULTURE_CHAMPION_V1", "params": {}}, indent=2))
    with tarfile.open(out, "w:gz", compresslevel=9) as tf:
        tf.add(main_py, arcname="main.py")
        tf.add(champion, arcname="champion.json")
    manifest = {
        "archive": out.name,
        "sha256": sha256(out),
        "members": ["main.py", "champion.json"],
        "main_sha256": sha256(main_py),
        "champion_sha256": sha256(champion),
    }
    (out.parent / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
