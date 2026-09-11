#!/usr/bin/env python3
"""Build a provenance-preserving JSONL corpus from approved GitHub sources.

This script clones repositories but NEVER installs dependencies, runs builds,
or executes code from upstream repositories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "sources.yaml"
CACHE = ROOT / ".cache" / "repos"

ALLOWED_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC0-1.0",
    "CC-BY-4.0",
    "Zlib",
    "MIT OR Apache-2.0",
}

TEXT_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".rst", ".adoc",
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".java", ".kt", ".kts",
    ".go", ".rs", ".rb", ".php", ".swift", ".dart", ".gd", ".lua",
    ".sh", ".bash", ".zsh", ".ps1", ".sql", ".html", ".css", ".scss",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
    ".proto", ".graphql", ".gql", ".vue", ".svelte", ".fountain",
}

EXCLUDED_DIRS = {
    ".git", ".github", ".idea", ".vscode", ".venv", "venv", "env",
    "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj",
    "coverage", ".next", ".nuxt", ".turbo", "__pycache__", ".pytest_cache",
    "third_party", "third-party", "thirdparty", "extern", "external",
    "assets", "images", "image", "icons", "fonts", "media", "screenshots",
    "artifacts", "checkpoints", "weights", "models", "datasets", "data/raw",
}

EXCLUDED_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock",
    "Cargo.lock", "composer.lock",
}

MAX_FILE_BYTES = 512_000
CHUNK_CHARS = 6_000
CHUNK_OVERLAP = 500


def run(cmd: list[str], *, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def load_registry() -> list[dict]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return data.get("sources", [])


def safe_repo_dir(repo: str) -> Path:
    return CACHE / repo.replace("/", "__")


def sync_repo(repo: str, destination: Path) -> str:
    url = f"https://github.com/{repo}.git"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (destination / ".git").exists():
        run(["git", "-C", str(destination), "fetch", "--depth=1", "origin"])
        run(["git", "-C", str(destination), "reset", "--hard", "FETCH_HEAD"])
        run(["git", "-C", str(destination), "clean", "-fdx"])
    else:
        if destination.exists():
            shutil.rmtree(destination)
        run([
            "git", "clone", "--depth=1", "--filter=blob:none", "--no-tags",
            url, str(destination)
        ])
    return run(["git", "-C", str(destination), "rev-parse", "HEAD"])


def is_excluded(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root)
    parts_lower = [p.lower() for p in rel.parts]
    for blocked in EXCLUDED_DIRS:
        blocked_parts = blocked.lower().split("/")
        if len(blocked_parts) == 1 and blocked_parts[0] in parts_lower:
            return True
        if len(blocked_parts) > 1:
            joined = "/".join(parts_lower)
            if blocked.lower() in joined:
                return True
    if path.name in EXCLUDED_FILENAMES:
        return True
    return False


def iter_text_files(repo_root: Path) -> Iterable[Path]:
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if is_excluded(path, repo_root):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS and path.name.lower() not in {
            "license", "readme", "contributing", "agents.md", "claude.md"
        }:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def chunks(text: str) -> Iterable[tuple[int, str]]:
    text = text.strip()
    if not text:
        return
    start = 0
    index = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            # Prefer a natural boundary near the chunk end.
            boundary = max(
                text.rfind("\n\n", start + CHUNK_CHARS // 2, end),
                text.rfind("\n", start + CHUNK_CHARS // 2, end),
            )
            if boundary > start:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            yield index, piece
            index += 1
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)


def eligible(source: dict, mode: str) -> tuple[bool, str]:
    if source.get("manual_approval"):
        return False, "manual approval required"
    license_name = source.get("license", "")
    if license_name not in ALLOWED_LICENSES:
        return False, f"license not auto-allowed: {license_name}"
    if not source.get(mode, False):
        return False, f"{mode}=false"
    if "/" not in source.get("repo", ""):
        return False, "not a concrete owner/repo"
    return True, "ok"


def build_record(source: dict, commit: str, path: Path, root: Path, idx: int, content: str) -> dict:
    rel = path.relative_to(root).as_posix()
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    repo = source["repo"]
    return {
        "category": source["category"],
        "repo": repo,
        "source_url": f"https://github.com/{repo}/blob/{commit}/{rel}",
        "commit": commit,
        "license": source["license"],
        "attribution_required": bool(source.get("attribution_required", False)),
        "path": rel,
        "chunk_index": idx,
        "sha256": digest,
        "content": content,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--category", action="append", help="Category to ingest; repeatable")
    group.add_argument("--all", action="store_true", help="Ingest every eligible source")
    parser.add_argument("--mode", choices=["rag", "training"], default="rag")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = load_registry()
    requested = set(args.category or [])
    selected = [s for s in sources if args.all or s.get("category") in requested]
    if not selected:
        print("No matching sources", file=sys.stderr)
        return 2

    approved: list[dict] = []
    for source in selected:
        ok, reason = eligible(source, args.mode)
        label = f"{source.get('category')} :: {source.get('repo')}"
        if ok:
            approved.append(source)
            print(f"[ALLOW] {label} :: {source.get('license')}")
        else:
            print(f"[SKIP ] {label} :: {reason}")

    if args.dry_run:
        print(f"Approved {len(approved)} of {len(selected)} selected sources")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.output.open("w", encoding="utf-8") as out:
        for source in approved:
            repo = source["repo"]
            repo_dir = safe_repo_dir(repo)
            try:
                commit = sync_repo(repo, repo_dir)
            except subprocess.CalledProcessError as exc:
                print(f"[ERROR] sync failed for {repo}: {exc}", file=sys.stderr)
                continue

            file_count = 0
            chunk_count = 0
            for path in iter_text_files(repo_dir):
                text = read_text(path)
                if not text:
                    continue
                file_count += 1
                for idx, piece in chunks(text):
                    record = build_record(source, commit, path, repo_dir, idx, piece)
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    written += 1
                    chunk_count += 1
            print(f"[DONE ] {repo} @ {commit[:12]} :: {file_count} files / {chunk_count} chunks")

    print(f"Corpus written: {args.output} ({written} chunks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
