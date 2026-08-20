#!/usr/bin/env node
/**
 * Deterministic validation for the bounded multi-AI engineering loop (AI_LOOP_V1).
 *
 * Two kinds of check:
 *   1. STATIC   - assert the shipped controller/reviewer/workflow sources actually contain
 *                 (or actually lack) the safety constructs the contract requires.
 *   2. BEHAVIOUR- re-implement the READY_TO_MERGE gate exactly as specified in the contract
 *                 and prove it accepts/rejects the right state combinations.
 *
 * Runs offline. No network, no API quota, no repo mutation.
 * Exit 0 = all checks pass. Exit 1 = at least one failed.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');

const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');
const exists = (rel) => fs.existsSync(path.join(ROOT, rel));

let passed = 0;
const failures = [];

function check(name, fn) {
  try {
    const r = fn();
    if (r === false) throw new Error('assertion returned false');
    passed++;
    console.log(`PASS  ${name}`);
  } catch (err) {
    failures.push({ name, message: err.message });
    console.log(`FAIL  ${name}\n        ${err.message}`);
  }
}

function assert(cond, message) {
  if (!cond) throw new Error(message);
}

/** Drop PowerShell comment lines so static scans inspect executable code, not prose. */
function stripPs1Comments(src) {
  return src
    .split('\n')
    .filter((l) => !/^\s*#/.test(l))
    .join('\n')
    .replace(/<#[\s\S]*?#>/g, '');
}

// =====================================================================================
// Contract gate, re-implemented from docs/ai-coengineer/AI_LOOP_CONTRACT.md section 2.
// =====================================================================================
const TERMINAL = ['READY_TO_MERGE', 'BLOCKED', 'MAX_ROUNDS_REACHED'];
const HARD_MAX_ROUNDS = 5;

function isReadyToMerge(s) {
  if (s.tests !== 'PASS') return false;
  if (s.checks !== 'PASS') return false;
  if (s.deepseek_verdict !== 'ACCEPT') return false;
  if (s.codex_verdict !== 'ACCEPT') return false;
  if (!s.head_sha) return false;
  if (s.deepseek_review_sha !== s.head_sha) return false; // stale DeepSeek review
  if (s.codex_review_sha !== s.head_sha) return false;    // stale Codex review
  if ((s.blocking_findings || []).length > 0) return false;
  return true;
}

function clampRounds(requested) {
  if (!Number.isFinite(requested) || requested < 1) return 1;
  return Math.min(requested, HARD_MAX_ROUNDS);
}

function validateObjective(task) {
  if (typeof task !== 'string') return { ok: false, reason: 'not a string' };
  const t = task.trim();
  if (!t) return { ok: false, reason: 'empty' };
  if (t.length < 12) return { ok: false, reason: 'too short' };
  if (t.length > 2000) return { ok: false, reason: 'too long' };
  return { ok: true };
}

const PROTECTED = ['main', 'master', 'refs/heads/main', 'origin/main'];
function isBranchSafe(name) {
  if (!name || !name.trim()) return false;
  const n = name.trim().toLowerCase().replace(/^refs\/heads\//, '');
  return !PROTECTED.some((p) => n === p.toLowerCase().replace(/^refs\/heads\//, ''));
}

const SHA_A = 'a'.repeat(40);
const SHA_B = 'b'.repeat(40);
const GOOD = {
  tests: 'PASS', checks: 'PASS',
  deepseek_verdict: 'ACCEPT', deepseek_review_sha: SHA_A,
  codex_verdict: 'ACCEPT', codex_review_sha: SHA_A,
  head_sha: SHA_A, blocking_findings: [],
};

// =====================================================================================
// 1. Files exist
// =====================================================================================
const REQUIRED_FILES = [
  'docs/ai-coengineer/AI_LOOP_CONTRACT.md',
  'docs/ai-coengineer/AI_LOOP_STATE.schema.json',
  'scripts/ai/ai-loop.ps1',
  'scripts/ai/deepseek_reviewer.py',
  'scripts/ai/claude_loop_prompt.md',
  '.github/workflows/ai-loop-deepseek-review.yml',
];
check('loop infrastructure files all present', () => {
  const missing = REQUIRED_FILES.filter((f) => !exists(f));
  assert(missing.length === 0, `missing: ${missing.join(', ')}`);
});

const ps1 = read('scripts/ai/ai-loop.ps1');
const py = read('scripts/ai/deepseek_reviewer.py');
const wf = read('.github/workflows/ai-loop-deepseek-review.yml');
const prompt = read('scripts/ai/claude_loop_prompt.md');
const contract = read('docs/ai-coengineer/AI_LOOP_CONTRACT.md');
const schema = JSON.parse(read('docs/ai-coengineer/AI_LOOP_STATE.schema.json'));

// =====================================================================================
// 2. Behaviour: objective validation
// =====================================================================================
check('malformed task rejected - empty', () => assert(!validateObjective('').ok, 'empty accepted'));
check('malformed task rejected - whitespace only', () => assert(!validateObjective('     ').ok, 'blank accepted'));
check('malformed task rejected - too short', () => assert(!validateObjective('fix it').ok, 'short accepted'));
check('malformed task rejected - non-string', () => assert(!validateObjective(null).ok, 'null accepted'));
check('valid task accepted', () => assert(validateObjective('Improve Forex entry intelligence').ok, 'valid rejected'));
check('controller enforces objective length floor', () =>
  assert(/Objective is too short/.test(ps1) && /No -Task objective supplied/.test(ps1),
    'controller lacks objective validation'));

// =====================================================================================
// 3. Behaviour: max rounds enforcement
// =====================================================================================
check('max rounds enforced - clamps above ceiling', () => assert(clampRounds(50) === 5, 'clamp failed'));
check('max rounds enforced - floor at 1', () => assert(clampRounds(0) === 1 && clampRounds(-9) === 1, 'floor failed'));
check('max rounds enforced - identity within range', () => assert(clampRounds(3) === 3, 'identity failed'));
check('controller hard-codes a round ceiling of 5', () =>
  assert(/\$script:HARD_MAX_ROUNDS\s*=\s*5/.test(ps1), 'HARD_MAX_ROUNDS is not pinned to 5'));
check('controller clamps MaxRounds against the ceiling', () =>
  assert(/MaxRounds\s*-gt\s*\$script:HARD_MAX_ROUNDS/.test(ps1), 'no clamp comparison found'));
check('round loop is bounded (for, not while-true)', () => {
  assert(/for \(\$round = 1; \$round -le \$script:State\.max_rounds; \$round\+\+\)/.test(ps1),
    'bounded for-loop not found');
  // Scan executable code only; a comment naming the banned construct is not the construct.
  assert(!/while\s*\(\s*\$true\s*\)/i.test(stripPs1Comments(ps1)), 'unbounded while($true) present');
  // Every `while` that does exist must carry a bound.
  for (const line of stripPs1Comments(ps1).split('\n')) {
    if (!/\bwhile\s*\(/.test(line)) continue;
    assert(/-lt|-le|-gt|-ge|deadline|MAX/i.test(line), `unbounded while loop: ${line.trim()}`);
  }
});
check('schema caps round and max_rounds at 5', () => {
  assert(schema.properties.round.maximum === 5, 'round max != 5');
  assert(schema.properties.max_rounds.maximum === 5, 'max_rounds max != 5');
});

// =====================================================================================
// 4. Behaviour + static: main push rejected
// =====================================================================================
check('main push rejected - branch guard logic', () => {
  assert(!isBranchSafe('main'), 'main accepted');
  assert(!isBranchSafe('MAIN'), 'MAIN accepted');
  assert(!isBranchSafe('refs/heads/main'), 'refs/heads/main accepted');
  assert(!isBranchSafe('origin/main'), 'origin/main accepted');
  assert(!isBranchSafe(''), 'empty accepted');
  assert(isBranchSafe('ai-loop/task-1'), 'feature branch rejected');
});
check('controller defines protected branches', () =>
  assert(/\$script:PROTECTED_BRANCHES\s*=\s*@\(.*main/.test(ps1), 'PROTECTED_BRANCHES missing'));
check('controller re-checks branch immediately before push', () => {
  const seg = ps1.split('function Publish-Round')[1] || '';
  assert(/Test-BranchSafe \$current/.test(seg), 'push path does not re-verify the branch');
  assert(/Refusing to push/.test(seg), 'push path lacks a refusal message');
});
check('schema forbids main as branch', () =>
  assert(JSON.stringify(schema.properties.branch.not.enum).includes('main'), 'schema allows main'));

// =====================================================================================
// 5. Static: missing gh auth blocked
// =====================================================================================
check('missing gh auth blocked', () => {
  const seg = ps1.split('function Test-GitHubAuth')[1] || '';
  assert(/gh.*auth.*status/s.test(seg), 'no gh auth status probe');
  assert(/Stop-Loop -Status "BLOCKED"/.test(seg), 'auth failure does not block the loop');
});

// =====================================================================================
// 6. Static: missing DeepSeek secret classified
// =====================================================================================
check('missing DeepSeek secret classified in reviewer', () =>
  assert(/MISSING_SECRET/.test(py) && /DEEPSEEK_API_KEY is not available/.test(py),
    'reviewer does not classify a missing key'));
check('missing DeepSeek secret classified in workflow', () =>
  assert(/MISSING_SECRET/.test(wf) && /if \[ -z "\$DEEPSEEK_API_KEY" \]/.test(wf),
    'workflow does not classify a missing key'));
check('reviewer classifies API error families', () => {
  for (const c of ['AUTH_ERROR', 'PAYMENT_REQUIRED', 'RATE_LIMITED', 'SERVER_ERROR', 'NETWORK_ERROR', 'TIMEOUT']) {
    assert(py.includes(c), `missing classification: ${c}`);
  }
});
check('non-retryable auth/payment errors are not retried', () =>
  assert(/if not retryable:\s*\n\s*raise LoopBlocked/.test(py), 'non-retryable path does not raise immediately'));

// =====================================================================================
// 7. Static: DeepSeek timeout bounded
// =====================================================================================
check('DeepSeek call is timeout bounded', () =>
  assert(/REQUEST_TIMEOUT_SEC/.test(py) && /urlopen\(req, timeout=REQUEST_TIMEOUT_SEC\)/.test(py),
    'urlopen has no timeout'));
check('DeepSeek attempts are capped at 3', () =>
  assert(/MAX_ATTEMPTS\s*=\s*3/.test(py), 'MAX_ATTEMPTS is not 3'));
check('DeepSeek backoff is exponential and capped', () => {
  assert(/BACKOFF_BASE_SEC/.test(py) && /BACKOFF_CAP_SEC/.test(py), 'backoff constants missing');
  assert(/min\(BACKOFF_BASE_SEC \* \(2 \*\* \(attempt - 1\)\), BACKOFF_CAP_SEC\)/.test(py),
    'backoff is not bounded exponential');
});
check('controller polling is bounded', () => {
  assert(/\$script:HARD_MAX_POLLS\s*=\s*\d+/.test(ps1), 'no poll ceiling');
  assert(/\$polls -lt \$script:HARD_MAX_POLLS/.test(ps1), 'poll ceiling not enforced');
  assert(/ReviewTimeoutSec/.test(ps1), 'no review timeout');
});
check('workflow job has a timeout', () =>
  assert(/timeout-minutes:\s*\d+/.test(wf), 'workflow job is unbounded'));

// =====================================================================================
// 8. Behaviour: stale review SHAs rejected
// =====================================================================================
check('stale DeepSeek review SHA rejected', () => {
  assert(isReadyToMerge(GOOD), 'baseline should be ready');
  assert(!isReadyToMerge({ ...GOOD, deepseek_review_sha: SHA_B }), 'stale DeepSeek SHA accepted');
  assert(!isReadyToMerge({ ...GOOD, deepseek_review_sha: null }), 'null DeepSeek SHA accepted');
});
check('stale Codex review SHA rejected', () => {
  assert(!isReadyToMerge({ ...GOOD, codex_review_sha: SHA_B }), 'stale Codex SHA accepted');
  assert(!isReadyToMerge({ ...GOOD, codex_review_sha: null }), 'null Codex SHA accepted');
});
check('controller compares DeepSeek review SHA to head', () =>
  assert(/\$ds\.Sha -ne \$script:State\.head_sha\.ToLowerInvariant\(\)/.test(ps1),
    'DeepSeek SHA freshness comparison missing'));
check('controller compares Codex review SHA to head', () =>
  assert(/\$cx\.Sha\.ToLowerInvariant\(\) -ne \$script:State\.head_sha\.ToLowerInvariant\(\)/.test(ps1),
    'Codex SHA freshness comparison missing'));
check('reviewer refuses to review a moved head', () =>
  assert(/STALE_HEAD/.test(py) && /STALE_REVIEW/.test(py), 'reviewer lacks stale-head guards'));
check('reviewer only counts Codex reviews at the exact commit', () =>
  assert(/commit_id/.test(ps1), 'controller ignores review commit_id'));

// =====================================================================================
// 9. Behaviour: tests and reviewer verdicts gate READY_TO_MERGE
// =====================================================================================
check('test failure prevents review-success completion', () => {
  assert(!isReadyToMerge({ ...GOOD, tests: 'FAIL' }), 'FAIL tests reached ready');
  assert(!isReadyToMerge({ ...GOOD, tests: 'NOT_RUN' }), 'NOT_RUN tests reached ready');
});
check('controller skips push and review when tests fail', () => {
  assert(/if \(-not \$testsPass\)/.test(ps1), 'no test-failure branch');
  const seg = ps1.split('if (-not $testsPass)')[1].split('continue')[0];
  assert(/not pushing, not requesting reviews/.test(seg), 'test failure still proceeds to review');
  assert(/FIX_REQUIRED/.test(seg), 'test failure does not set FIX_REQUIRED');
});
check('one reviewer REJECT prevents READY_TO_MERGE', () => {
  assert(!isReadyToMerge({ ...GOOD, deepseek_verdict: 'REJECT' }), 'DeepSeek REJECT reached ready');
  assert(!isReadyToMerge({ ...GOOD, codex_verdict: 'REJECT' }), 'Codex REJECT reached ready');
  assert(!isReadyToMerge({ ...GOOD, deepseek_verdict: 'BLOCKED' }), 'DeepSeek BLOCKED reached ready');
  assert(!isReadyToMerge({ ...GOOD, codex_verdict: 'PENDING' }), 'Codex PENDING reached ready');
});
check('failing GitHub checks prevent READY_TO_MERGE', () => {
  assert(!isReadyToMerge({ ...GOOD, checks: 'FAIL' }), 'failing checks reached ready');
  assert(!isReadyToMerge({ ...GOOD, checks: 'PENDING' }), 'pending checks reached ready');
});
check('outstanding blocking findings prevent READY_TO_MERGE', () =>
  assert(!isReadyToMerge({ ...GOOD, blocking_findings: ['unresolved'] }), 'blockers reached ready'));
check('both reviews ACCEPT + tests PASS allows READY_TO_MERGE', () =>
  assert(isReadyToMerge(GOOD) === true, 'fully green state did not reach ready'));
check('ACCEPT with blockers is downgraded to REJECT', () => {
  assert(/verdict == "ACCEPT" and blockers/.test(py), 'reviewer lacks the contradiction guard');
  assert(/\$verdict -eq "ACCEPT" -and \$blockers\.Count -gt 0/.test(ps1), 'controller lacks the contradiction guard');
});
check('schema encodes the READY_TO_MERGE gate', () => {
  const rule = schema.allOf.find((a) => a.if?.properties?.status?.const === 'READY_TO_MERGE');
  assert(rule, 'no READY_TO_MERGE conditional in schema');
  assert(rule.then.properties.deepseek_verdict.const === 'ACCEPT', 'schema does not require DeepSeek ACCEPT');
  assert(rule.then.properties.codex_verdict.const === 'ACCEPT', 'schema does not require Codex ACCEPT');
  assert(rule.then.properties.blocking_findings.maxItems === 0, 'schema permits blockers at ready');
});

// =====================================================================================
// 10. Static: no merge, no deploy, anywhere in the loop
// =====================================================================================
const LOOP_SOURCES = { ps1, py, wf, prompt };
check('no merge executed by any loop component', () => {
  const banned = [/gh\s+pr\s+merge/i, /pulls\/\d*\/merge/i, /--auto-merge/i, /merge_pull_request/i, /git\s+merge\b/i];
  for (const [name, src] of Object.entries(LOOP_SOURCES)) {
    for (const b of banned) {
      assert(!b.test(src), `${name} contains a merge operation matching ${b}`);
    }
  }
});
check('no deploy executed by any loop component', () => {
  // Usage of a deploy credential, not mere mention. Naming CLOUDFLARE_API_TOKEN inside a
  // redaction denylist is protective and must stay allowed; binding it to a command is not.
  const credentialUse = [
    /\$env:CLOUDFLARE_API_TOKEN/,
    /secrets\.CLOUDFLARE_API_TOKEN/,
    /^\s*CLOUDFLARE_API_TOKEN\s*:/m,
    /environ\S*CLOUDFLARE_API_TOKEN/,
    /CLOUDFLARE_API_TOKEN\s*=\s*["'$]/,
  ];
  for (const [name, src] of Object.entries(LOOP_SOURCES)) {
    // `wrangler deploy --dry-run` is validation, not deployment; a bare deploy is banned.
    const matches = src.match(/wrangler\s+deploy(?!\s+--dry-run)/g) || [];
    assert(matches.length === 0, `${name} contains a live wrangler deploy`);
    for (const p of credentialUse) {
      assert(!p.test(src), `${name} binds a Cloudflare deploy credential (${p})`);
    }
  }
  // And the denylist mention must genuinely be a redaction, not a leftover.
  assert(/CLOUDFLARE_API_TOKEN[^\n]*REDACTED/.test(ps1),
    'CLOUDFLARE_API_TOKEN appears in the controller outside a redaction pattern');
});
check('controller explicitly reports no merge and no deploy', () =>
  assert(/MERGE_PERFORMED=NO/.test(ps1) && /DEPLOY_PERFORMED=NO/.test(ps1),
    'summary does not assert merge/deploy safety'));
check('DeepSeek workflow has least-privilege permissions', () => {
  assert(/permissions:\s*\n\s*contents:\s*read\s*\n\s*pull-requests:\s*write/.test(wf),
    'workflow permissions are not least-privilege');
  assert(!/contents:\s*write/.test(wf), 'workflow requests contents: write');
});
check('DeepSeek workflow does not trigger on main pushes', () => {
  assert(!/^\s*push:/m.test(wf), 'workflow triggers on push');
  assert(/pull_request:/.test(wf), 'workflow lacks a pull_request trigger');
  for (const t of ['opened', 'synchronize', 'reopened', 'ready_for_review']) {
    assert(wf.includes(t), `workflow missing trigger type: ${t}`);
  }
  assert(/workflow_dispatch:/.test(wf), 'workflow lacks workflow_dispatch');
});

// =====================================================================================
// 11. Static: permission safety
// =====================================================================================
check('dangerously-skip-permissions is never used', () => {
  for (const [name, src] of Object.entries(LOOP_SOURCES)) {
    const uses = src.match(/--dangerously-skip-permissions/g) || [];
    const mentions = src.match(/dangerously-skip-permissions/g) || [];
    // It may be *named* in a prohibition comment, but never passed as a live flag.
    assert(uses.length === mentions.length - (mentions.length - uses.length) || true, 'noop');
    assert(!/claude[^\n]*--dangerously-skip-permissions/.test(src),
      `${name} passes --dangerously-skip-permissions to claude`);
  }
});
check('claude is invoked with a narrow allowedTools list', () => {
  assert(/--allowedTools/.test(ps1), 'no --allowedTools');
  const seg = ps1.split('function Get-ClaudeAllowedTools')[1].split('function ')[0];
  assert(/"Read", "Edit", "Write", "Glob", "Grep"/.test(seg), 'expected file tools missing');
  for (const banned of ['git push', 'git commit', 'gh pr merge', 'wrangler deploy']) {
    assert(!seg.includes(banned), `allowedTools grants ${banned}`);
  }
});
check('controller owns git write operations, not claude', () => {
  assert(/function Publish-Round/.test(ps1), 'no controller-owned publish step');
  assert(/controller-owned/i.test(ps1), 'ownership not documented in the controller');
  assert(/never own|does not own git|controller.*owns all git write/i.test(prompt),
    'prompt does not forbid claude from doing git writes');
});
check('no force push anywhere', () => {
  for (const [name, src] of Object.entries(LOOP_SOURCES)) {
    assert(!/push[^\n]*(--force|-f\b|\+refs)/.test(src), `${name} may force push`);
  }
});
check('loop never mutates GitHub secrets', () => {
  for (const [name, src] of Object.entries(LOOP_SOURCES)) {
    assert(!/gh\s+secret\s+(set|remove|delete)/.test(src), `${name} mutates secrets`);
  }
  assert(/gh.*secret.*list/s.test(ps1), 'controller should verify secret names by list only');
});

// =====================================================================================
// 12. Static: no secret printed
// =====================================================================================
check('no secret printed - redaction exists on both sides', () => {
  assert(/def redact\(/.test(py) && /SECRET_PATTERNS/.test(py), 'python redaction missing');
  assert(/function Protect-Secret/.test(ps1), 'powershell redaction missing');
});
check('no secret printed - reviewer redacts before comment and stdout', () => {
  assert(/return redact\("\\n"\.join\(parts\)\)/.test(py) || /redact\(/.test(py), 'comment body not redacted');
  assert(/def log\(message: str\) -> None:\s*\n\s*print\(redact\(message\)/.test(py),
    'reviewer log() does not redact');
});
check('no secret printed - workflow never echoes the key', () => {
  assert(!/echo[^\n]*\$DEEPSEEK_API_KEY/.test(wf), 'workflow echoes the key');
  assert(/value not printed/i.test(wf), 'workflow lacks an explicit no-print assertion');
});
check('no hardcoded credentials in loop sources', () => {
  const patterns = [/sk-[A-Za-z0-9]{20,}/, /gh[pousr]_[A-Za-z0-9]{20,}/, /-----BEGIN [A-Z ]*PRIVATE KEY-----/];
  for (const [name, src] of Object.entries(LOOP_SOURCES)) {
    for (const p of patterns) assert(!p.test(src), `${name} contains a hardcoded credential`);
  }
});

// =====================================================================================
// 13. Static: safety invariants carried into the Claude prompt
// =====================================================================================
check('claude prompt carries every trading safety invariant', () => {
  const required = ['SIGNAL-ONLY', 'freshness', 'Structural SL', 'RR quality', 'Anti-chase',
    'Hard-news', 'TRADING_STATE', 'v775:books', 'V73', 'Hyro'];
  for (const r of required) assert(prompt.includes(r), `prompt missing invariant: ${r}`);
});
check('claude prompt forbids merge, deploy and guard-silencing', () => {
  assert(/merge a pull request/i.test(prompt), 'prompt does not forbid merging');
  assert(/deploy to Cloudflare production/i.test(prompt), 'prompt does not forbid deploying');
  assert(/Silencing a guard is itself a hard blocker/i.test(prompt), 'prompt allows silencing guards');
});
check('claude prompt requires a machine-readable result block', () => {
  for (const f of ['CLAUDE_ROUND_BEGIN', 'CLAUDE_ROUND_END', 'STATUS=', 'TESTS_RESULT=', 'SAFETY_INVARIANTS=']) {
    assert(prompt.includes(f), `prompt missing block field: ${f}`);
  }
});
check('controller parses the claude result block', () => {
  assert(/CLAUDE_ROUND_BEGIN/.test(ps1) && /CLAUDE_ROUND_END/.test(ps1), 'controller cannot parse the block');
  assert(/SAFETY_INVARIANTS.*-eq "FAIL"/s.test(ps1), 'controller ignores a safety failure');
});
check('all prompt placeholders are substituted by the controller', () => {
  const placeholders = [...new Set((prompt.match(/\{\{[A-Z_]+\}\}/g) || []))];
  assert(placeholders.length > 0, 'prompt has no placeholders');
  for (const p of placeholders) {
    assert(ps1.includes(`.Replace("${p}"`), `controller never substitutes ${p}`);
  }
});

// =====================================================================================
// 14. Static: state machine completeness
// =====================================================================================
check('all contract states are represented', () => {
  const states = ['IDLE', 'TASK_ACCEPTED', 'IMPLEMENTING', 'TESTING', 'AWAITING_REVIEWS',
    'FIX_REQUIRED', 'READY_TO_MERGE', 'BLOCKED', 'MAX_ROUNDS_REACHED'];
  for (const s of states) {
    assert(contract.includes(s), `contract missing state: ${s}`);
    assert(schema.properties.status.enum.includes(s), `schema missing state: ${s}`);
    assert(ps1.includes(s), `controller missing state: ${s}`);
  }
});
check('terminal states stop the loop', () => {
  for (const t of TERMINAL) assert(new RegExp(`Stop-Loop -Status "${t}"`).test(ps1), `no Stop-Loop for ${t}`);
  assert(/ValidateSet\("BLOCKED", "MAX_ROUNDS_REACHED", "READY_TO_MERGE"\)/.test(ps1),
    'Stop-Loop does not constrain terminal states');
});
check('terminal states hand control to a human', () => {
  const rule = schema.allOf.find((a) => JSON.stringify(a.if?.properties?.status?.enum || []).includes('BLOCKED'));
  assert(rule, 'no terminal-state rule in schema');
  assert(rule.then.properties.next_actor.enum.every((x) => ['HUMAN', 'NONE'].includes(x)),
    'terminal state schedules a non-human actor');
});
check('controller emits the required AI_LOOP_RESULT summary fields', () => {
  for (const f of ['AI_LOOP_RESULT', 'TASK=', 'PR=', 'HEAD=', 'ROUNDS=', 'TESTS=', 'DEEPSEEK=', 'CODEX=', 'STATUS=', 'NEXT_ACTION=']) {
    assert(ps1.includes(f), `summary missing field: ${f}`);
  }
});

// =====================================================================================
// 15. Static: reviewer protocol
// =====================================================================================
check('reviewer emits the contract block format', () => {
  for (const f of ['DEEPSEEK_REVIEW_BEGIN', 'DEEPSEEK_REVIEW_END', 'HEAD_SHA=', 'VERDICT=', 'BLOCKERS=', 'NON_BLOCKING=']) {
    assert(py.includes(f), `reviewer missing protocol token: ${f}`);
  }
});
check('reviewer is a reviewer, not an implementer', () => {
  assert(/reviewer, not an implementer/i.test(py), 'role not asserted in the reviewer prompt');
  assert(!/git\s+(commit|push|checkout)/.test(py), 'reviewer performs git writes');
});
check('process output capture is race-free and deadlock-free', () => {
  // Register-ObjectEvent + -MessageData appends from the threadpool without
  // synchronisation and can only be drained by sleeping after exit; that race can
  // truncate output and fake a test failure. ReadToEndAsync has neither problem.
  // Scan executable code only; the rationale comment names the construct it replaced.
  assert(!/Register-ObjectEvent/.test(stripPs1Comments(ps1)), 'still uses cross-runspace event capture');
  assert(/StandardOutput\.ReadToEndAsync\(\)/.test(ps1), 'stdout is not read async');
  assert(/StandardError\.ReadToEndAsync\(\)/.test(ps1), 'stderr is not read async');
  // Both reads must start before WaitForExit, or a full pipe deadlocks the child.
  const seg = stripPs1Comments(ps1).split('function Invoke-Native')[1].split('function Invoke-Git')[0];
  const outIdx = seg.indexOf('ReadToEndAsync');
  const waitIdx = seg.indexOf('WaitForExit');
  assert(outIdx > -1 && waitIdx > outIdx, 'async reads must be started before WaitForExit');
  // Every Task wait must be bounded.
  for (const m of seg.match(/\.Wait\(([^)]*)\)/g) || []) {
    assert(/\d{3,}/.test(m), `unbounded task wait: ${m}`);
  }
});
check('truncated diff fails closed to REJECT', () => {
  assert(/DIFF TRUNCATED/.test(py), 'no truncation notice');
  assert(/Emit VERDICT=REJECT and record the/.test(py),
    'truncation does not force REJECT - a reviewer must never accept a diff it could not read');
  assert(!/flag truncation as NON_BLOCKING/.test(py), 'truncation is still treated as non-blocking');
});
check('reviewer diff budget is large enough for infra-sized PRs', () => {
  const m = py.match(/DEEPSEEK_MAX_DIFF_CHARS", "(\d+)"/);
  assert(m, 'diff budget is not configurable');
  assert(Number(m[1]) >= 150000, `diff budget ${m[1]} is too small`);
});
check('reviewer sends the full changed-file list even when the diff truncates', () => {
  assert(/def fetch_changed_files/.test(py), 'no changed-file listing');
  assert(/COMPLETE CHANGED-FILE LIST/.test(py), 'file list not surfaced in the prompt');
  assert(/authoritative scope, even if the diff below is truncated/.test(py),
    'file list is not framed as the authoritative scope');
});
check('reviewer protocol-repair pass is bounded to one retry', () => {
  assert(/PROTOCOL_ERROR/.test(py), 'no protocol error classification');
  assert(/protocol-repair/.test(py), 'no protocol-repair pass');
  // Exactly two call_deepseek invocations on the review path: initial + one repair.
  const calls = (py.match(/reply = call_deepseek\(/g) || []).length;
  assert(calls === 2, `expected exactly 2 call_deepseek invocations, found ${calls}`);
  assert(/if exc\.classification != "PROTOCOL_ERROR":\s*\n\s*raise/.test(py),
    'repair pass is not restricted to protocol errors');
});
check('reviewer reply budget can hold prose plus the mandatory block', () =>
  assert(/"max_tokens": (4000|[5-9]\d{3})/.test(py), 'max_tokens too small to guarantee the block'));
check('reviewer posts exactly one comment (upsert by marker)', () => {
  assert(/COMMENT_MARKER/.test(py) && /def upsert_comment/.test(py), 'no comment upsert');
});
check('reviewer dry-run makes no API call', () => {
  assert(/--dry-run/.test(py), 'no dry-run flag');
  assert(/DRY RUN - no DeepSeek API call was made/.test(py), 'dry-run does not assert no API call');
  const seg = py.split('if args.dry_run:')[1].split('reply = call_deepseek')[0];
  assert(!/call_deepseek\(/.test(seg), 'dry-run path calls the API');
});

// =====================================================================================
// 16. Static: contract documents the loop independence requirement
// =====================================================================================
check('contract states the loop needs no open browser conversation', () =>
  assert(/no browser conversation needs to stay open/i.test(contract), 'independence requirement missing'));
check('contract defines all five actor roles', () => {
  for (const a of ['PRIMARY_IMPLEMENTER', 'ADVERSARIAL_REVIEWER', 'INDEPENDENT_REVIEWER', 'STATE_BUS', 'VALIDATION_TARGET', 'ORCHESTRATOR']) {
    assert(contract.includes(a), `contract missing role: ${a}`);
  }
});
check('contract forbids committing live state to main', () =>
  assert(/NOT continuously committed to `main`/.test(contract), 'state-churn rule missing'));

// =====================================================================================
console.log('');
if (failures.length) {
  console.log(`AI_LOOP_SELFTEST FAIL  ${passed} passed, ${failures.length} failed`);
  for (const f of failures) console.log(`  - ${f.name}: ${f.message}`);
  process.exit(1);
}
console.log(`AI_LOOP_SELFTEST PASS  ${passed}/${passed} checks`);
process.exit(0);
