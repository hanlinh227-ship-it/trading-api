#!/usr/bin/env python3
import argparse
import getpass
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

SECRET_PATTERNS = [
    re.compile(r"\b(xprv|tprv)[1-9A-HJ-NP-Za-km-z]{20,}\b"),
    re.compile(r"\b[5KL][1-9A-HJ-NP-Za-km-z]{50,51}\b"),
]
FORBIDDEN_SUFFIXES = {'.dat','.wallet','.ldb','.sqlite','.sqlite3','.key','.pem','.seed','.mnemonic','.xprv','.wif','.secret','.bak','.backup'}


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def ensure_outside_repo(path: pathlib.Path, repo_root: pathlib.Path):
    rp = path.resolve()
    rr = repo_root.resolve()
    try:
        rp.relative_to(rr)
        raise RuntimeError('Output/input secret-bearing path must be outside the Git repository.')
    except ValueError:
        return


def scan_repo(repo_root: pathlib.Path):
    findings = []
    for p in repo_root.rglob('*'):
        if '.git' in p.parts or not p.is_file():
            continue
        if p.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(str(p.relative_to(repo_root)))
            continue
        if p.stat().st_size > 1024 * 1024:
            continue
        try:
            txt = p.read_text(errors='ignore')
        except Exception:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(txt):
                findings.append(str(p.relative_to(repo_root)))
                break
    if findings:
        raise RuntimeError('Potential secret material detected inside repository: ' + ', '.join(sorted(set(findings))))


def verify_bitcoin_core_known_passphrase(wallet_name: str, rpc_args: list[str]) -> dict:
    candidate = getpass.getpass('Known wallet passphrase candidate (input hidden): ')
    if not candidate:
        raise RuntimeError('Empty candidate.')
    cmd = ['bitcoin-cli', *rpc_args, f'-rpcwallet={wallet_name}', 'walletpassphrase', candidate, '2']
    try:
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
    finally:
        candidate = None
    ok = cp.returncode == 0
    if ok:
        subprocess.run(['bitcoin-cli', *rpc_args, f'-rpcwallet={wallet_name}', 'walletlock'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    return {'mode':'bitcoin_core_known_passphrase','matched':ok,'detail':'candidate accepted' if ok else 'candidate rejected'}


def main():
    ap = argparse.ArgumentParser(description='Owner-authorized, local-only BTC wallet recovery verifier. No brute force.')
    ap.add_argument('--backup', help='Path to owner-supplied local backup file')
    ap.add_argument('--expected-sha256')
    ap.add_argument('--report', required=True, help='Sanitized JSON report path outside the repo')
    ap.add_argument('--wallet-name', help='Loaded Bitcoin Core wallet name for known-passphrase verification')
    ap.add_argument('--rpc-arg', action='append', default=[], help='Optional bitcoin-cli RPC argument, e.g. -rpcconnect=127.0.0.1')
    ap.add_argument('--attest-owned', action='store_true', help='Confirm the wallet is owned by or authorized to the operator')
    args = ap.parse_args()

    if not args.attest_owned:
        raise RuntimeError('Ownership/authorization attestation is required.')

    repo_root = pathlib.Path(__file__).resolve().parent.parent
    scan_repo(repo_root)

    report_path = pathlib.Path(args.report)
    ensure_outside_repo(report_path, repo_root)
    report = {
        'protocol':'BTC_WALLET_RECOVERY_V1',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'ownership_attested': True,
        'checks': []
    }

    if args.backup:
        bp = pathlib.Path(args.backup)
        ensure_outside_repo(bp, repo_root)
        if not bp.is_file():
            raise RuntimeError('Backup file not found.')
        digest = sha256_file(bp)
        item = {'mode':'backup_integrity','sha256':digest,'size':bp.stat().st_size}
        if args.expected_sha256:
            item['expected_match'] = digest.lower() == args.expected_sha256.lower()
        report['checks'].append(item)

    if args.wallet_name:
        report['checks'].append(verify_bitcoin_core_known_passphrase(args.wallet_name, args.rpc_arg))

    if not report['checks']:
        raise RuntimeError('No recovery check selected.')

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'ok':True,'report':str(report_path),'checks':len(report['checks'])}))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(json.dumps({'ok':False,'error':str(e)}))
        sys.exit(2)
