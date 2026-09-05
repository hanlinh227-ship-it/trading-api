#!/usr/bin/env bash
set -euo pipefail
sed -n '130,220p' /opt/meme-alpha/app/run-paper.sh | nl -ba -v130
