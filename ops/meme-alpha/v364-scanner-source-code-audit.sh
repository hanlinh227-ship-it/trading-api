#!/usr/bin/env bash
set -euo pipefail
SC=/opt/meme-alpha/app/src/scanner.js
echo '=== V364 SCANNER SOURCE CODE AUDIT ==='
sed -n '1,490p' "$SC"
echo V364_SCANNER_SOURCE_CODE_AUDIT=COMPLETE
