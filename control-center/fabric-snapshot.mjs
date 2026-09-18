// Runtime Fabric view for the Control Tower.
//
// This module READS the canonical acceptance matrix. It does not re-derive it.
// A second derivation of FULL_ACTIVE would be a second evidence authority, and
// two derivations of one fact eventually disagree - at which point the
// dashboard and the fabric would both be "the" answer. So: run the canonical
// tool, parse its JSON, label each row, show it. Nothing else.
//
// If the canonical tool cannot run, the snapshot is UNAVAILABLE. There is no
// cached-guess fallback and no partial matrix: a fabric view that keeps
// rendering after it stopped being able to read the fabric is the exact lie
// this file exists to prevent.

import { execFile } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { PROVENANCE } from './provenance.mjs';

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ACCEPTANCE_TOOL = path.resolve(
  __dirname, '..', 'AI_SKILL_LIBRARY', 'v4', 'runtime_fabric', 'acceptance.py');

const PYTHON = process.env.CC_PYTHON || 'python3';
const TIMEOUT_MS = 10_000;
const MAX_OUTPUT_BYTES = 256 * 1024;

// Rows whose value is a CI gate outcome for THIS run. Absent means NOT_OBSERVED,
// which the canonical tool already spells out; we never round it to PASS.
const GATE_ROWS = new Set([
  'PRIMARY_DEPLOY', 'PRIMARY_HEALTH', 'PRIMARY_SHA_MATCH', 'LIVE_RESEARCH_SMOKE',
]);

// Rows that are policy declared in the registry, not an observation of a system.
const POLICY_ROWS = new Set([
  'ZERO_COST_GUARD', 'RAILWAY_REQUIRED', 'PERSONAL_PC_REQUIRED', 'PAID_FALLBACK',
]);

// Rows that merely name a thing rather than assert a state about it.
const IDENTITY_ROWS = new Set([
  'PRIMARY_RUNTIME', 'SECONDARY_RUNTIME', 'TERTIARY_RUNTIME',
]);

/**
 * Provenance of one matrix row.
 *
 * Registry-backed rows are HISTORICAL_EVIDENCE, not REAL_LIVE: they record a
 * verification that happened on some earlier run. The Tower is not probing
 * these runtimes, and saying REAL_LIVE would claim that it is.
 */
export function rowProvenance(key, value) {
  if (IDENTITY_ROWS.has(key)) return PROVENANCE.CONFIGURED;
  if (POLICY_ROWS.has(key)) return PROVENANCE.CONFIGURED;
  if (GATE_ROWS.has(key)) {
    return value === 'NOT_OBSERVED' ? PROVENANCE.NOT_OBSERVED : PROVENANCE.HISTORICAL_EVIDENCE;
  }
  if (key === 'FAILOVER_PROOF') {
    // SIMULATED_ONLY is selection logic, not a served failover. It is not
    // evidence of anything having run, so it must not read as evidence.
    if (value === 'SIMULATED_ONLY' || value === 'UNVERIFIED') return PROVENANCE.UNVERIFIED;
    return PROVENANCE.HISTORICAL_EVIDENCE;
  }
  if (key === 'FULL_ACTIVE') {
    // FULL_ACTIVE is a conjunction over gates that are NOT_OBSERVED here. Its
    // falseness is real; its truth could only be as live as its weakest input.
    return value === true ? PROVENANCE.HISTORICAL_EVIDENCE : PROVENANCE.NOT_OBSERVED;
  }
  return PROVENANCE.HISTORICAL_EVIDENCE;
}

// Keys that are structure rather than a single asserted value. They are
// surfaced as their own shapes, not squeezed into a scalar row.
export const STRUCTURAL_KEYS = new Set([
  'BLOCKERS', 'STABLE_RUNTIMES', 'DEVELOPMENT_LAB_RUNTIMES', 'RUNTIME_LIFECYCLES',
]);

export function labelMatrix(matrix) {
  const rows = [];
  for (const key of Object.keys(matrix).sort()) {
    if (STRUCTURAL_KEYS.has(key)) continue;
    rows.push({ key, value: matrix[key], provenance: rowProvenance(key, matrix[key]) });
  }
  return rows;
}

/**
 * Run the canonical tool and return a labelled snapshot.
 * Never throws: an unreadable fabric is reported, not raised.
 */
export async function fabricSnapshot({ tool = ACCEPTANCE_TOOL, python = PYTHON } = {}) {
  const observed_at = new Date().toISOString();
  try {
    const { stdout } = await execFileAsync(python, [tool, '--json'], {
      timeout: TIMEOUT_MS,
      maxBuffer: MAX_OUTPUT_BYTES,
      encoding: 'utf8',
    });
    const matrix = JSON.parse(stdout);
    if (!matrix || typeof matrix !== 'object' || Array.isArray(matrix)) {
      throw new Error('acceptance matrix was not a JSON object');
    }
    return {
      status: 'OK',
      observed_at,
      source: 'AI_SKILL_LIBRARY/v4/runtime_fabric/acceptance.py --json',
      authority: 'RUNTIME_FABRIC_V2',
      rows: labelMatrix(matrix),
      blockers: Array.isArray(matrix.BLOCKERS) ? matrix.BLOCKERS : [],
      // Lifecycle is recorded verification, so it is HISTORICAL_EVIDENCE: the
      // Tower is reading what was established, not probing these runtimes now.
      lifecycles: {
        provenance: PROVENANCE.HISTORICAL_EVIDENCE,
        stable: Array.isArray(matrix.STABLE_RUNTIMES) ? matrix.STABLE_RUNTIMES : [],
        development_lab: Array.isArray(matrix.DEVELOPMENT_LAB_RUNTIMES) ? matrix.DEVELOPMENT_LAB_RUNTIMES : [],
        by_runtime: (matrix.RUNTIME_LIFECYCLES && typeof matrix.RUNTIME_LIFECYCLES === 'object') ? matrix.RUNTIME_LIFECYCLES : {},
      },
    };
  } catch (err) {
    return {
      status: 'UNAVAILABLE',
      observed_at,
      source: 'AI_SKILL_LIBRARY/v4/runtime_fabric/acceptance.py --json',
      authority: 'RUNTIME_FABRIC_V2',
      reason: String(err?.message || err).slice(0, 500),
      rows: [],
      blockers: [],
      lifecycles: { provenance: PROVENANCE.NOT_OBSERVED, stable: [], development_lab: [], by_runtime: {} },
    };
  }
}
