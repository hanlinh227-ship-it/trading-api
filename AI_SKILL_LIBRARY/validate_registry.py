#!/usr/bin/env python3
"""Validate AI Skill Library source registry and optional upstream state."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
REGISTRY = ROOT / 'sources.yaml'
CHECKPOINT_MANIFEST = ROOT / 'checkpoint.json'

ALLOWED_CATEGORIES = {'game', 'ux_ui', 'prompt', 'script', 'code', 'trading', 'software'}
ALLOWED_LICENSES = {
    'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause',
    'CC0-1.0', 'CC-BY-4.0', 'Zlib', 'MIT OR Apache-2.0',
}
REQUIRED_FIELDS = {'category', 'repo', 'license', 'rag', 'training', 'focus'}
REPO_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def validate_registry_data(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ['registry root must be a mapping'], warnings
    if data.get('version') != 1:
        errors.append('registry version must be 1')
    sources = data.get('sources')
    if not isinstance(sources, list) or not sources:
        errors.append('sources must be a non-empty list')
        return errors, warnings

    seen: dict[str, int] = {}
    for idx, source in enumerate(sources, start=1):
        prefix = f'source[{idx}]'
        if not isinstance(source, dict):
            errors.append(f'{prefix}: entry must be a mapping')
            continue
        missing = sorted(REQUIRED_FIELDS - set(source))
        if missing:
            errors.append(f"{prefix}: missing fields: {', '.join(missing)}")
            continue

        category = source.get('category')
        repo = source.get('repo')
        license_name = source.get('license')
        manual = bool(source.get('manual_approval', False))

        if category not in ALLOWED_CATEGORIES:
            errors.append(f'{prefix}: unknown category {category!r}')
        if not isinstance(repo, str) or not repo.strip():
            errors.append(f'{prefix}: repo must be a non-empty string')
        elif not manual and not REPO_RE.match(repo):
            errors.append(f'{prefix}: active repo must be owner/repo: {repo!r}')
        if not manual and license_name not in ALLOWED_LICENSES:
            errors.append(f'{prefix}: license not auto-approved: {license_name!r}')
        if manual and (source.get('rag') or source.get('training')):
            errors.append(f'{prefix}: manual_approval entries must keep rag=false and training=false')
        if not isinstance(source.get('rag'), bool) or not isinstance(source.get('training'), bool):
            errors.append(f'{prefix}: rag and training must be booleans')
        if not isinstance(source.get('focus'), str) or not source.get('focus', '').strip():
            errors.append(f'{prefix}: focus must be non-empty text')

        if isinstance(repo, str):
            key = repo.lower()
            if key in seen:
                errors.append(f'{prefix}: duplicate repo {repo!r}; first seen at source[{seen[key]}]')
            else:
                seen[key] = idx

        if source.get('status') == 'archived':
            warnings.append(f'{prefix}: {repo} is intentionally marked archived')

    return errors, warnings


def validate_checkpoint() -> tuple[list[str], list[str]]:
    """Keep registry compatibility checks small; brain structure is validated elsewhere."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = json.loads(CHECKPOINT_MANIFEST.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return ['checkpoint.json is missing'], warnings
    except json.JSONDecodeError as exc:
        return [f'checkpoint.json invalid JSON: {exc}'], warnings

    checkpoint_id = manifest.get('checkpoint_id')
    if checkpoint_id not in {'GITHUB_BRAIN_V2', 'GITHUB_BRAIN_V3'}:
        errors.append("checkpoint.checkpoint_id must be 'GITHUB_BRAIN_V2' or 'GITHUB_BRAIN_V3'")

    expected = {
        'canonical_repo': 'hanlinh227-ship-it/trading-api',
        'canonical_branch': 'main',
        'registry_path': 'AI_SKILL_LIBRARY/sources.yaml',
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append(f'checkpoint.{key} must be {value!r}')

    expected_checkpoint_path = {
        'GITHUB_BRAIN_V2': 'AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md',
        'GITHUB_BRAIN_V3': 'AI_SKILL_LIBRARY/GITHUB_BRAIN_V3.md',
    }.get(checkpoint_id)
    cp_path = manifest.get('checkpoint_path')
    if expected_checkpoint_path and cp_path != expected_checkpoint_path:
        errors.append(f'checkpoint.checkpoint_path must be {expected_checkpoint_path!r}')
    if not isinstance(cp_path, str) or not cp_path:
        errors.append('checkpoint.checkpoint_path must be set')
    else:
        resolved = (REPO_ROOT / cp_path).resolve()
        try:
            resolved.relative_to(REPO_ROOT.resolve())
        except ValueError:
            errors.append('checkpoint_path must stay inside repository')
        else:
            if not resolved.is_file():
                errors.append(f'checkpoint target is missing: {cp_path}')
            else:
                text = resolved.read_text(encoding='utf-8')
                if 'GitHub-first' not in text or 'router.yaml' not in text or 'sources.yaml' not in text:
                    errors.append('checkpoint target must define GitHub-first routing, router.yaml and sources.yaml')
    return errors, warnings


def _github_json(url: str, token: str | None) -> dict:
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ai-skill-library-validator'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def check_remote_sources(data: dict, token: str | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for idx, source in enumerate(data.get('sources', []), start=1):
        if source.get('manual_approval'):
            continue
        repo = source.get('repo', '')
        if not REPO_RE.match(repo):
            continue
        url = f'https://api.github.com/repos/{repo}'
        try:
            meta = _github_json(url, token)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                errors.append(f'source[{idx}]: upstream repo not found: {repo}')
            else:
                warnings.append(f'source[{idx}]: GitHub HTTP {exc.code} checking {repo}')
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            warnings.append(f'source[{idx}]: remote check unavailable for {repo}: {exc}')
            continue

        canonical = meta.get('full_name')
        if canonical and canonical.lower() != repo.lower():
            warnings.append(f'source[{idx}]: {repo} canonical name is now {canonical}')
        if meta.get('archived') and source.get('status') != 'archived':
            warnings.append(f'source[{idx}]: {repo} is archived upstream')
        remote_license = (meta.get('license') or {}).get('spdx_id')
        expected = source.get('license')
        if remote_license and remote_license != 'NOASSERTION':
            accepted = {expected}
            if expected == 'MIT OR Apache-2.0':
                accepted |= {'MIT', 'Apache-2.0'}
            if remote_license not in accepted:
                warnings.append(
                    f'source[{idx}]: license metadata differs for {repo}: registry={expected}, github={remote_license}'
                )
        elif not remote_license:
            warnings.append(f'source[{idx}]: GitHub exposes no SPDX license metadata for {repo}')
    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-remote', action='store_true')
    parser.add_argument('--fail-on-warning', action='store_true')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = yaml.safe_load(REGISTRY.read_text(encoding='utf-8'))
    except FileNotFoundError:
        print(f'[ERROR] missing registry: {REGISTRY}', file=sys.stderr)
        return 2
    except yaml.YAMLError as exc:
        print(f'[ERROR] invalid YAML: {exc}', file=sys.stderr)
        return 2

    errors, warnings = validate_registry_data(data)
    cp_errors, cp_warnings = validate_checkpoint()
    errors.extend(cp_errors)
    warnings.extend(cp_warnings)
    if args.check_remote:
        remote_errors, remote_warnings = check_remote_sources(data, os.getenv('GITHUB_TOKEN'))
        errors.extend(remote_errors)
        warnings.extend(remote_warnings)

    for warning in warnings:
        print(f'[WARN ] {warning}')
    for error in errors:
        print(f'[ERROR] {error}', file=sys.stderr)
    print(f'Validation summary: {len(errors)} error(s), {len(warnings)} warning(s)')
    if errors or (args.fail_on_warning and warnings):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
