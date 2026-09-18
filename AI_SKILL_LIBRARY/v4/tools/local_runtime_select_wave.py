"""Select a bounded, diverse wave from the prefetch index into the transport manifest.

    python AI_SKILL_LIBRARY/v4/tools/local_runtime_select_wave.py --index .model-staging/prefetch-index.json --write

Prefetch is deliberately broad; admission is deliberately not. The architecture
brief asks for bounded waves of a few models chosen for capability diversity,
not for every artifact that was staged - "20-40 genuinely complementary models
are more valuable than hundreds of near-duplicate binaries".

So this selects rather than imports. Two rules, both stated in the output for
every model so a deferral can be argued with:

* a size ceiling, because disk is finite and a 5 GB artifact must earn its
  place against the host's free space rather than arrive by default;
* one model per publisher family per wave, so a wave cannot fill itself with
  variants of the same thing.

Selection grants nothing. Every selected entry still enters the pipeline at
transport state and must earn licence, scan, format, runtime and capability
evidence of its own. Notably the prefetch index carries no licence for any
model - the discovery step did not populate it - so none of these can be
admitted until the metadata fetch supplies one. That is recorded as a gap, not
filled in from what the family is generally known to use.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

MANIFEST_REL = "AI_SKILL_LIBRARY/v4/open_model_universe/staging_manifest.json"

#: Tier ceilings from the architecture brief, in bytes.
TIER_S = 1_000_000_000
TIER_A = 3_000_000_000
TIER_B = 6_000_000_000


def tier_of(size_bytes: int) -> str:
    if size_bytes < TIER_S:
        return "S"
    if size_bytes <= TIER_A:
        return "A"
    if size_bytes <= TIER_B:
        return "B"
    return "C"


def slug(repo_id: str, filename: str) -> str:
    quant = re.search(r"(?<![A-Za-z0-9])(I?Q\d+(?:_[0-9A-Za-z]+)*|BF16|F16|F32|i2_s)(?![A-Za-z0-9])",
                      filename or "", re.IGNORECASE)
    base = repo_id.split("/")[-1].lower().replace("_", "-")
    tag = (quant.group(1).lower() if quant else "unknown")
    return re.sub(r"[^a-z0-9.-]+", "-", f"{base}-{tag}").strip("-")


def family_of(repo_id: str) -> str:
    """Group near-duplicates so one wave cannot be six variants of one model."""
    name = repo_id.split("/")[-1].lower()
    for marker in ("smollm2", "qwen3-vl", "qwen3-coder", "qwen3", "gemma", "granite",
                   "ministral", "mistral", "phi-3", "phi", "bitnet", "olmo", "deepseek"):
        if marker in name:
            return marker
    return name


def select(index: Mapping[str, Any], *, max_bytes: int, max_models: int,
           per_family: int) -> tuple[list[dict], list[dict]]:
    rows = sorted(
        (e for e in index.get("entries") or [] if e.get("weights_present_in_artifact")),
        key=lambda e: int(e.get("size_bytes") or 0),
    )
    chosen: list[dict] = []
    deferred: list[dict] = []
    per_family_count: dict[str, int] = {}

    for entry in rows:
        size = int(entry.get("size_bytes") or 0)
        family = family_of(str(entry.get("repo_id")))
        reason = None
        if size > max_bytes:
            reason = (f"tier {tier_of(size)} at {size // 1048576} MB exceeds this wave's "
                      f"{max_bytes // 1048576} MB ceiling")
        elif per_family_count.get(family, 0) >= per_family:
            reason = f"already selected a {family} model this wave; prefer a different family"
        elif len(chosen) >= max_models:
            reason = f"wave is bounded at {max_models} models"

        if reason:
            deferred.append({"repo_id": entry["repo_id"], "size_bytes": size,
                             "tier": tier_of(size), "deferred_because": reason})
            continue

        per_family_count[family] = per_family_count.get(family, 0) + 1
        chosen.append(entry)

    return chosen, deferred


def manifest_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    repo = str(entry["repo_id"])
    filename = str(entry["filename"])
    size = int(entry["size_bytes"])
    return {
        "id": slug(repo, filename),
        "family": repo.split("/")[-1].split("-")[0],
        "variant": filename.rsplit(".", 1)[0],
        "hf_repo": repo,
        "filename": filename,
        "source_run_id": int(entry["source_run_id"]),
        "artifact_name": str(entry["artifact_name"]),
        "expected_sha256": str(entry["sha256"]).lower(),
        "size_bytes": size,
        "immutable_revision": entry.get("immutable_revision"),
        # Stronger than Wave 1's recovered revision: the prefetch job pinned the
        # repo's commit at discovery and downloaded from resolve/<revision>, so
        # the bytes demonstrably came from it rather than from a moving ref.
        "revision_status": "pinned_at_download",
        "size_tier": tier_of(size),
        "release_tag": f"staged-model-{slug(repo, filename)}",
        "license_gap": ("the prefetch index declares no licence for this repo; it must be "
                        "fetched before admission and is never inferred from the family"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="select a bounded wave")
    parser.add_argument("--root", type=Path, default=repo_root)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--max-mb", type=int, default=2500)
    parser.add_argument("--max-models", type=int, default=6)
    parser.add_argument("--per-family", type=int, default=1)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    index = json.loads(args.index.read_text(encoding="utf-8"))
    chosen, deferred = select(index, max_bytes=args.max_mb * 1048576,
                              max_models=args.max_models, per_family=args.per_family)
    entries = [manifest_entry(row) for row in chosen]

    written: list[str] = []
    if args.write and entries:
        manifest_path = args.root / MANIFEST_REL
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        have = {e["expected_sha256"] for e in manifest["entries"]}
        for entry in entries:
            # Never add a model whose bytes are already tracked.
            if entry["expected_sha256"] in have:
                continue
            manifest["entries"].append(entry)
            written.append(entry["id"])
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    payload = {
        "wave": index.get("wave"),
        "selected": len(entries),
        "deferred": len(deferred),
        "total_selected_bytes": sum(e["size_bytes"] for e in entries),
        "written_to_manifest": written,
        "admits_nothing": True,
        "entries": entries,
        "deferrals": deferred,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
