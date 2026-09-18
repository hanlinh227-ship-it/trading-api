#!/usr/bin/env bash
#
# Regenerate the canonical Golden E2E evidence on a host that can actually run
# the engine, then return it to the branch.
#
#   bash AI_SKILL_LIBRARY/v4/tools/regenerate_golden_evidence.sh
#
# WHY THIS EXISTS
#
# `ai_core_release_gate` reports AI_CORE_RELEASE=FAIL 8/9. The single failing
# check is `golden_e2e`, with `semantic_answer_mismatch`: the committed evidence
# answers "What is the capital of France?" with Paris, while the canonical
# golden request asks about Japan. There are exactly two ways to clear that, and
# one of them - editing the recorded answer - is precisely what the check exists
# to catch. This script is the other one.
#
# It cannot be run in the container that produced it. `detect_llama_cpp_python`
# raises SIGILL there (exit 132, uncatchable), which is the same fact that makes
# round V of the 24x7 proof and round J of the free-worker proof unmeasurable.
# The preflight below refuses rather than producing a document that would look
# like a real run.
#
# NOTHING HERE FAKES A RUN. It binds the revision and the model artifact digest,
# drives the real chain, and re-checks the result with the same verifier that is
# currently refusing. If the model does not say Tokyo, the gate stays red and
# this script exits non-zero.

set -euo pipefail

REQUEST="What is the capital city of Japan? Answer briefly."
EXPECTED_MODEL="Qwen/Qwen3-4B-GGUF"
EXPECTED_SHA256="7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
EXPECTED_REVISION="bc640142c66e1fdd12af0bd68f40445458f3869b"
BRANCH="claude/magical-euler-uu98r8"
EVIDENCE="CHECKPOINTS/evidence/B3_B4_GOLDEN_E2E_EVIDENCE.json"

cd "$(git rev-parse --show-toplevel)"

echo "== 0. bind the revision =================================================="
git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"
SOURCE_SHA="$(git rev-parse HEAD)"
echo "SOURCE_SHA=${SOURCE_SHA}"
if ! git diff --quiet; then
  echo "REFUSED: the working tree is dirty; evidence must name a clean revision"
  exit 1
fi

echo "== 1. preflight: can this host execute the engine at all? ================"
# In a subprocess, because SIGILL is not an exception and an in-process probe
# takes the prober down with it.
python3 AI_SKILL_LIBRARY/v4/tools/worker_execution_liveness.py \
  --evidence CHECKPOINTS/evidence/WORKER_EXECUTION_LIVENESS.json
STATE="$(python3 -c "import json;print(json.load(open('CHECKPOINTS/evidence/WORKER_EXECUTION_LIVENESS.json'))['execution_liveness'])")"
echo "WORKER_EXECUTION_LIVENESS=${STATE}"
if [ "${STATE}" != "EXECUTION_LIVE" ]; then
  echo "REFUSED: this host reports ${STATE}. Run this on a host whose inference"
  echo "engine executes. Regenerating evidence here would record a run that did"
  echo "not happen."
  exit 1
fi

echo "== 2. bind the model artifact ==========================================="
python3 - "${EXPECTED_MODEL}" "${EXPECTED_SHA256}" "${EXPECTED_REVISION}" <<'PY'
import sys, yaml
model_id, sha256, revision = sys.argv[1:4]
rows = yaml.safe_load(open("AI_SKILL_LIBRARY/v4/open_model_universe/registry.yaml"))["models"]
row = next((r for r in rows if r.get("model_id") == model_id), None)
if row is None:
    raise SystemExit("REFUSED: %s is not in the registry" % model_id)
identity = row.get("artifact_identity") or {}
if identity.get("sha256") != sha256 or identity.get("immutable_revision") != revision:
    raise SystemExit(
        "REFUSED: the registry's artifact for %s no longer matches the digest this "
        "script was written against. Regenerate against the current artifact "
        "deliberately rather than silently." % model_id)
print("ARTIFACT_MODEL=%s" % model_id)
print("ARTIFACT_SHA256=%s" % sha256)
print("ARTIFACT_REVISION=%s" % revision)
PY

echo "== 3. run the canonical chain =========================================="
# task_router -> AI Legion -> Model Mesh -> scheduler -> admitted local model
# -> real inference -> semantic verifier -> synthesis -> evidence. The tool owns
# that ordering; this only supplies the canonical request.
python3 AI_SKILL_LIBRARY/v4/tools/local_runtime_ai_core_e2e.py \
  --request "${REQUEST}" \
  --evidence "${EVIDENCE}"

echo "== 4. re-check the answer with the verifier that is refusing today ======"
python3 - "${EVIDENCE}" <<'PY'
import json, sys
sys.path.insert(0, ".")
from AI_SKILL_LIBRARY.v4.local_runtime.golden_e2e import (
    CANONICAL_GOLDEN_REQUEST, make_verifier)
evidence = json.load(open(sys.argv[1]))
report = make_verifier(CANONICAL_GOLDEN_REQUEST)(
    "core_reasoning", evidence["runtime_evidence"])
print("SEMANTIC_GOLDEN_VERIFIED=%s" % report["passed"])
for failure in report["failures"]:
    print("  %s" % failure)
if not report["passed"]:
    raise SystemExit(
        "REFUSED: the run completed and its answer still does not satisfy the "
        "canonical oracle. Do not edit the answer. Investigate the model or the "
        "request; the gate is correct to stay red.")
PY

echo "== 5. rerun the release gate and the two federation proofs =============="
python3 AI_SKILL_LIBRARY/v4/tools/federation_24x7_proof.py \
  --evidence CHECKPOINTS/evidence/FEDERATION_24X7_PROOF.json || true
python3 AI_SKILL_LIBRARY/v4/tools/free_worker_mesh_proof.py \
  --evidence CHECKPOINTS/evidence/FREE_WORKER_MESH_PROOF.json || true
python3 AI_SKILL_LIBRARY/v4/tools/federation_status_scopes.py \
  --evidence CHECKPOINTS/evidence/FEDERATION_STATUS_SCOPES.json
python3 AI_SKILL_LIBRARY/v4/tools/ai_core_release_gate.py

echo "== 6. return the evidence to the branch ================================"
# Evidence only. No file under AI_SKILL_LIBRARY/ moves, so each document's
# source_sha keeps describing the code it was run against.
git add CHECKPOINTS/evidence
git commit -m "evidence(ai-core): regenerate golden E2E from a real run on a live engine

Produced by AI_SKILL_LIBRARY/v4/tools/regenerate_golden_evidence.sh against
source_sha ${SOURCE_SHA} on a host reporting EXECUTION_LIVE, using
${EXPECTED_MODEL} at sha256 ${EXPECTED_SHA256}. The semantic verifier was
re-run against the canonical request and passed before this commit was made."
git push origin "HEAD:${BRANCH}"

echo "DONE. Re-check CI on ${BRANCH}; AI_CORE_RELEASE should now report 9/9."
