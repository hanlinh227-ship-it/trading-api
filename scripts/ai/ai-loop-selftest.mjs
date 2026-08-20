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
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// AI_LOOP_SELFTEST_ROOT lets a TRUSTED copy of this suite audit an UNTRUSTED tree.
//
// This file is writable under the loop's lock, so on any PR it is code the change under
// review controls. Running the head's own copy would let a malicious change rewrite its
// own assertions to pass - the suite would then prove nothing about that change. Pointing
// a base-revision copy at the head's files instead keeps the assertions trusted while the
// subject stays untrusted, mirroring how the reviewer runs from base.
//
// Unset, it audits its own checkout, which is the correct behaviour locally.
const ROOT = process.env.AI_LOOP_SELFTEST_ROOT
  ? path.resolve(process.env.AI_LOOP_SELFTEST_ROOT)
  : path.resolve(HERE, '..', '..');

// Normalise CRLF. A fresh checkout on a machine with core.autocrlf=true yields \r\n, and
// several checks match on '\n' or split on it - so without this the suite passes in the
// working tree and fails on a clean clone, which is precisely when it matters most.
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8').replace(/\r\n/g, '\n');
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
  assert(/gh auth login/.test(seg), 'no actionable remediation for a real logout');
});
check('auth probe separates a real logout from a network blip', () => {
  const seg = ps1.split('function Test-GitHubAuth')[1].split('function Update-Base')[0];
  assert(/not logged \(in\|into\)|not logged/.test(seg), 'does not detect a genuine logout');
  assert(/dial tcp|network is unreachable/.test(seg), 'does not detect a transient network error');
  // Retry must be bounded.
  assert(/for \(\$attempt = 1; \$attempt -le 3; \$attempt\+\+\)/.test(seg), 'auth retry is not bounded to 3');
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
check('controller compares DeepSeek review SHA to head', () => {
  assert(/\$ds\.Sha\.ToLowerInvariant\(\) -ne \$script:State\.head_sha\.ToLowerInvariant\(\)/.test(ps1),
    'DeepSeek SHA freshness comparison missing');
  assert(/\$null -eq \$ds\.Sha -or/.test(ps1), 'a null DeepSeek SHA is not treated as stale');
});
check('controller compares Codex review SHA to head', () => {
  assert(/\$cx\.Sha\.ToLowerInvariant\(\) -ne \$script:State\.head_sha\.ToLowerInvariant\(\)/.test(ps1),
    'Codex SHA freshness comparison missing');
  assert(/\$null -eq \$cx\.Sha -or/.test(ps1), 'a null Codex SHA is not treated as stale');
});
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
  // Scan EXECUTABLE code only. Rationale comments legitimately name the operations they
  // exist to defend against - the workflow history guard has to explain `git merge -s ours`
  // to justify --full-history - and a comment is not an invocation.
  const executable = {
    ps1: stripPs1Comments(ps1),
    py: py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n'),
    wf: wf.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n'),
    prompt,
  };
  for (const [name, src] of Object.entries(executable)) {
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
  // A same-line `claude ... --flag` regex is too weak: a multi-line invocation, an
  // argument array, or a variable would slip past it. Assert instead that the flag does
  // not appear in EXECUTABLE code at all; it may only be named in prohibition prose.
  const executable = {
    ps1: stripPs1Comments(ps1),
    py: py.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n'),
    wf: wf.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n'),
  };
  for (const [name, src] of Object.entries(executable)) {
    assert(!/--dangerously-skip-permissions/.test(src),
      `${name} references --dangerously-skip-permissions in executable code`);
  }
  // And it must never reach the allowedTools list under any spelling.
  const seg = ps1.split('function Get-ClaudeAllowedTools')[1].split('function ')[0];
  assert(!/dangerously/i.test(seg), 'allowedTools mentions the skip-permissions flag');
});
check('allowedTools does not grant arbitrary execution via npm scripts', () => {
  const seg = stripPs1Comments(ps1).split('function Get-ClaudeAllowedTools')[1].split('function ')[0];
  // npm scripts are arbitrary code defined in package.json.
  assert(!/npm test/.test(seg), 'allowedTools grants npm test, which runs arbitrary package scripts');
  assert(!/npm run|npx |Bash\(npm/.test(seg), 'allowedTools grants an npm/npx escape hatch');
});
check('claude is invoked with a narrow allowedTools list', () => {
  assert(/--allowedTools/.test(ps1), 'no --allowedTools');
  const seg = stripPs1Comments(ps1).split('function Get-ClaudeAllowedTools')[1].split('function ')[0];
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
check('the reviewer never silently drops part of a diff', () => {
  // Superseded by chunking: nothing is truncated any more, so no partial-read path can
  // reach a verdict at all. Assert the old truncation behaviour is fully gone.
  assert(!/DIFF TRUNCATED/.test(py), 'truncation notice still present alongside chunking');
  assert(!/diff\[:MAX_DIFF_CHARS\] \+ \(/.test(py), 'diff is still truncated before review');
  assert(!/flag truncation as NON_BLOCKING/.test(py), 'truncation treated as non-blocking');
  // The whole diff must reach the splitter, which is the only place size is handled.
  const seg = py.split('def fetch_diff')[1].split('\ndef ')[0];
  assert(/return proc\.stdout or ""/.test(seg), 'fetch_diff does not return the complete diff');
  assert(!/MAX_DIFF_CHARS/.test(seg), 'fetch_diff still applies a size limit of its own');
});
check('an oversized single file splits at hunk boundaries, never mid-hunk', () => {
  // Slicing one file at raw byte offsets cuts hunks in half and hands the reviewer
  // malformed diff text, which can hide or invent defects.
  assert(/def _split_file_diff/.test(py), 'no hunk-aware splitter');
  const seg = py.split('def _split_file_diff')[1].split('\ndef ')[0];
  assert(/re\.split\(r"\(\?m\)\^\(\?=@@ \)"/.test(seg), 'does not split at @@ hunk boundaries');
  assert(/header \+ hunk/.test(seg), 'file header is not repeated on each piece');
  // The old byte-offset slicer must be gone.
  assert(!/range\(0, len\(part\), MAX_DIFF_CHARS\)/.test(py), 'byte-offset slicing still present');
});
check('total request count is bounded across a chunked review', () => {
  assert(/MAX_TOTAL_REQUESTS/.test(py), 'no total request cap');
  assert(/_TOTAL_REQUESTS\[0\] >= MAX_TOTAL_REQUESTS/.test(py), 'cap is never enforced');
  assert(/REQUEST_BUDGET_EXHAUSTED/.test(py), 'exhausted total budget is not classified');
  // reset_attempts must NOT reset the per-review total.
  // Match the assignment, not a mention: MAX_TOTAL_REQUESTS contains _TOTAL_REQUESTS.
  const seg = py.split('def reset_attempts')[1].split('\ndef ')[0];
  assert(!/_TOTAL_REQUESTS\[0\]\s*=/.test(seg), 'per-chunk reset also clears the whole-review budget');
  assert(/_ATTEMPTS_USED\[0\] = 0/.test(seg), 'per-chunk reset does not clear the attempt budget');
});
check('same-named checks from different suites are all evaluated', () => {
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  // This repo publishes two check runs named `validate` from different workflows.
  assert(/Group-Object/.test(seg), 'checks are not grouped by suite');
  assert(/\.suite/.test(seg), 'check suite identity is not considered');
  assert(/check_suite\.id/.test(ps1), 'check-run query does not fetch the suite id');
});
check('polling never sleeps past its deadline', () => {
  const seg = ps1.split('function Wait-ForReviews')[1];
  assert(/Math\]::Min\(\$PollIntervalSec, \$remaining\)/.test(seg), 'sleep is not clamped to the deadline');
  assert(/\$remaining -le 0\) \{ break \}/.test(seg), 'no break when the deadline has passed');
});
check('abandoned output capture is reported, not silently truncated', () => {
  const seg = ps1.split('function Invoke-Native')[1].split('function Invoke-Git')[0];
  assert(/capture did not complete within/.test(seg), 'a timed-out capture is silently dropped');
  assert(!/try \{ if \(\$outTask\.Wait\(15000\)\)/.test(seg), 'capture timeout is still swallowed by catch');
});
check('total review coverage is large enough for infra-sized PRs', () => {
  // The budget bounds ONE CHUNK, not the whole diff - chunking handles size now. It is
  // sized for the model's reliability rather than its context limit: 160k-char chunks fit
  // in context but produced two consecutive PROTOCOL_ERROR failures because the mandatory
  // block never appeared. What must remain generous is chunks x budget, the total coverage
  // before a PR is declared too large to review.
  const perChunk = Number((py.match(/DEEPSEEK_MAX_DIFF_CHARS", "(\d+)"/) || [])[1]);
  const chunks = Number((py.match(/DEEPSEEK_MAX_DIFF_CHUNKS", "(\d+)"/) || [])[1]);
  assert(Number.isFinite(perChunk) && Number.isFinite(chunks), 'chunk budget is not configurable');
  assert(perChunk >= 40000, `per-chunk budget ${perChunk} is too small to hold a meaningful unit of diff`);
  assert(perChunk <= 120000, `per-chunk budget ${perChunk} is large enough to degrade instruction-following`);
  assert(perChunk * chunks >= 400000,
    `total coverage ${perChunk * chunks} is too small for an infrastructure-sized PR`);
  // The request budget must be able to service every chunk at least once.
  const totalReq = Number((py.match(/DEEPSEEK_MAX_TOTAL_REQUESTS", "(\d+)"/) || [])[1]);
  assert(totalReq >= chunks * 2,
    `request budget ${totalReq} cannot service ${chunks} chunks with a repair pass each`);
});
check('oversized diffs are chunked, not silently truncated', () => {
  // Truncate-and-reject was correct but made any PR past the budget permanently
  // unreviewable, and raising the budget only defers the same wall.
  assert(/def split_diff/.test(py), 'no diff chunking');
  assert(/MAX_DIFF_CHUNKS/.test(py), 'chunk count is unbounded');
  assert(/re\.split\(r"\(\?m\)\^\(\?=diff --git \)"/.test(py),
    'chunks are not split at file boundaries, so hunks could be cut in half');
  assert(/DIFF_TOO_LARGE/.test(py), 'a diff beyond the chunk cap is not classified');
  assert(/fetch_diff.*\n.*Return the COMPLETE diff/.test(py) || /Return the COMPLETE diff/.test(py),
    'fetch_diff no longer returns the complete diff');
});
check('an oversized hunk is split into valid sub-hunks, not refused or oversized', () => {
  // An ADDED FILE is one hunk covering the whole file, so "hunk larger than the budget" is
  // the normal case here, not a pathological one - refusing it made the reviewer useless
  // on exactly the PRs that most need reviewing. Emitting it whole would reproduce the
  // PROTOCOL_ERROR the budget exists to prevent. So it is split, with each piece carrying
  // a recomputed @@ header describing precisely the lines it contains.
  assert(/def _split_hunk/.test(py), 'oversized hunks are not split');
  const seg = py.split('def _split_hunk')[1].split('\ndef ')[0];
  assert(/_HUNK_HEADER_RE/.test(py), 'hunk headers are never parsed');
  assert(/old_pos \+= old_count/.test(seg) && /new_pos \+= new_count/.test(seg),
    'sub-hunk start offsets do not accumulate, so headers would be wrong');
  assert(/header_reserve/.test(seg),
    'packing does not reserve space for the header each piece carries, so pieces overshoot');
  // Counts must be derived from content, both sides.
  assert(/old_count \+= 1/.test(seg) && /new_count \+= 1/.test(seg),
    'line counts are not derived from the piece content');
  assert(/startswith\("\\\\\\\\"\)/.test(seg) || /startswith\('\\\\\\\\'\)/.test(seg) || /No newline/.test(seg),
    'the "\\ No newline at end of file" marker is not handled');
  // The caller splits rather than refusing, and only fails when a single LINE cannot fit.
  const caller = py.split('def _split_file_diff')[1].split('\ndef ')[0];
  assert(/_split_hunk\(hunk,/.test(caller), 'the caller does not split an oversized hunk');
  assert(/longest single line/.test(caller),
    'the unfittable case is not reported in terms of the offending line');
  // The exact remainder, not a floor. A floor lets _split_hunk pack past the real budget
  // and then trip HUNK_TOO_LARGE even though every individual line fits.
  assert(/remaining = MAX_DIFF_CHARS - len\(header\)/.test(caller),
    'the caller does not pass the exact remaining budget');
  assert(!/max\(1024, MAX_DIFF_CHARS/.test(caller), 'a budget floor still overrides the remainder');
  assert(/BUDGET_TOO_SMALL/.test(caller), 'a budget leaving no room for the header is not rejected');
  // A "\ No newline at end of file" marker is only meaningful attached to the line before
  // it; flushing between them emits a zero-count hunk that is not a self-consistent diff.
  assert(/not ln\.startswith/.test(seg), 'a split can orphan the no-newline marker');
});
check('chunked verdicts merge with rejection winning', () => {
  assert(/def merge_results/.test(py), 'no verdict merge');
  const seg = py.split('def merge_results')[1].split('\ndef ')[0];
  assert(/verdict = "BLOCKED"/.test(seg), 'BLOCKED does not propagate');
  assert(/verdict = "REJECT"/.test(seg), 'REJECT does not propagate');
  assert(/if blockers and verdict == "ACCEPT"/.test(seg),
    'a chunk reporting blockers could still merge to ACCEPT');
  // Each chunk must get its own bounded attempt budget, not share one across the review.
  assert(/def reset_attempts/.test(py), 'no per-chunk attempt reset');
  assert(/reset_attempts\(\)\s*\n\s*reply = call_deepseek/.test(py),
    'attempt budget is not reset per chunk');
});
check('reviewer sends the full changed-file list even when the diff truncates', () => {
  assert(/def fetch_changed_files/.test(py), 'no changed-file listing');
  assert(/COMPLETE CHANGED-FILE LIST/.test(py), 'file list not surfaced in the prompt');
  assert(/authoritative scope, even if the diff below is truncated/.test(py),
    'file list is not framed as the authoritative scope');
});
check('the verdict block is emitted first, so it cannot be lost', () => {
  // With the block last, a long analysis runs out of reply budget before reaching it and
  // the entire review becomes unusable - which is exactly what happened at fa2055e, on
  // both the first attempt and the repair pass.
  assert(/Your reply MUST BEGIN with the machine-readable block/.test(py),
    'the block is not demanded first');
  assert(/It must be the FIRST thing in your reply/.test(py), 'block-first is not stated as a rule');
  assert(!/end your reply with exactly one machine-readable block/.test(py),
    'the old block-last instruction is still present');
  // Commentary is then whatever follows the block, not what precedes it.
  assert(/reply\.split\(END, 1\)\[-1\]/.test(py), 'prose is still taken from before the block');
  assert(!/reply\.split\(BEGIN, 1\)\[0\]\)/.test(py), 'prose extraction still assumes block-last');
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
check('HTTP attempts are capped across the WHOLE review, not per call', () => {
  // Two invocations of a 3-attempt loop would allow 6 requests; the contract says 3.
  assert(/_ATTEMPTS_USED/.test(py), 'no shared attempt counter');
  assert(/def attempts_remaining/.test(py), 'no shared budget accessor');
  assert(/budget = attempts_remaining\(\)/.test(py), 'retry loop does not consume the shared budget');
  assert(/for attempt in range\(1, budget \+ 1\)/.test(py), 'retry loop is not bounded by the shared budget');
  assert(!/for attempt in range\(1, MAX_ATTEMPTS \+ 1\)/.test(py), 'per-call attempt loop still present');
  assert(/ATTEMPTS_EXHAUSTED/.test(py), 'exhausted budget is not classified');
});
check('DeepSeek verdict comments are authenticated', () => {
  const seg = ps1.split('function Get-DeepSeekVerdict')[1].split('function Get-Codex')[0];
  assert(/\$script:REVIEW_BOT_LOGIN/.test(seg), 'verdict author is not verified');
  // Controller and reviewer must agree on the identity, or a valid verdict would be
  // refused and the loop would stall at PENDING.
  assert(/REVIEW_BOT_LOGIN\s*=.*github-actions\[bot\]/.test(ps1), 'controller bot identity is not pinned');
  assert(/AI_LOOP_BOT_LOGIN/.test(ps1) && /AI_LOOP_BOT_LOGIN/.test(py),
    'controller and reviewer do not share the same bot-identity override');
  assert(/ai-loop:deepseek-review/.test(seg), 'reviewer comment marker is not verified');
  assert(/login: \.user\.login/.test(seg), 'comment author is not even fetched');
  // A forged ACCEPT from any PR participant must be ignored, not trusted.
  assert(/ignoring a DEEPSEEK_REVIEW block from/.test(seg), 'forged verdicts are not rejected');
});
check('write-lock scope is enforced before testing or staging', () => {
  // Owner-only verification is not enough: Publish-Round runs `git add -A`, so an
  // out-of-scope edit would otherwise be committed, up to Trading business source.
  assert(/function Assert-ChangesInLockScope/.test(ps1), 'no lock-scope enforcement');
  assert(/function Test-PathInLockScope/.test(ps1), 'no per-path scope test');
  assert(/\$script:AllowedPaths/.test(ps1), 'allowed paths are never parsed from the lock');
  // Must run before both the test step and the staging step.
  const body = stripPs1Comments(ps1);
  const assertIdx = body.indexOf('Assert-ChangesInLockScope\n');
  const testIdx = body.indexOf('$testsPass = Invoke-DeterministicTests');
  const pubIdx = body.indexOf('$pushed = Publish-Round');
  assert(assertIdx > -1 && testIdx > assertIdx, 'scope check does not precede the tests');
  assert(pubIdx > assertIdx, 'scope check does not precede staging');
  assert(/outside the declared WRITE_LOCK scope/.test(ps1), 'out-of-scope files are not refused');
  // The parser must read only the allowed-scope section: scanning the whole lock file also
  // harvests backticked bullets from the Protocol prose, and a prose bullet naming a real
  // path would silently authorise it.
  assert(/allowed\\s\+scope/.test(ps1), 'scope parsing is not restricted to its section');
  assert(/\$inScopeSection/.test(ps1), 'no section tracking while parsing the lock');
  assert(/-notmatch '\^-'/.test(ps1), 'flag-like prose entries are not rejected');
});
check('skipped reviewers are never synthesised into acceptance', () => {
  // Either switch previously produced an exact-head ACCEPT, satisfying the READY gate
  // without the contractually required independent review.
  assert(!/if \(\$SkipDeepSeek\) \{ \$ds = \[pscustomobject\]@\{ Verdict = "ACCEPT"/.test(ps1),
    'SkipDeepSeek still fabricates an ACCEPT');
  assert(!/if \(\$SkipCodex\) \{ \$cx = \[pscustomobject\]@\{ Verdict = "ACCEPT"/.test(ps1),
    'SkipCodex still fabricates an ACCEPT');
  assert(/if \(\$SkipDeepSeek\) \{ \$ds = \[pscustomobject\]@\{ Verdict = "PENDING"/.test(ps1),
    'SkipDeepSeek does not hold the verdict at PENDING');
  assert(/if \(\$SkipCodex\) \{ \$cx = \[pscustomobject\]@\{ Verdict = "PENDING"/.test(ps1),
    'SkipCodex does not hold the verdict at PENDING');
  // And the switches must not be usable on a live run at all.
  assert(/-SkipDeepSeek is a rehearsal switch/.test(ps1), 'SkipDeepSeek is allowed on a live run');
  assert(/-SkipCodex is a rehearsal switch/.test(ps1), 'SkipCodex is allowed on a live run');
  // SHA freshness must no longer be conditional on the switches.
  assert(!/if \(-not \$SkipDeepSeek\) \{ if \(\$ds\.Sha/.test(ps1), 'DeepSeek SHA freshness is skippable');
  assert(!/if \(-not \$SkipCodex\)\s+\{ if \(\$null -eq \$cx\.Sha/.test(ps1), 'Codex SHA freshness is skippable');
});
check('PR head is revalidated immediately before declaring readiness', () => {
  const seg = ps1.split('if ($bothAccepted -and $shaFresh')[1].split('if ($checks.Status -eq "FAIL")')[0];
  assert(/headRefOid/.test(seg), 'live head is not refetched before returning READY');
  assert(/PR head advanced to/.test(seg), 'an advanced head does not fail closed');
  assert(/could not revalidate the live PR head/.test(seg), 'an unconfirmable head does not fail closed');
  const readyIdx = seg.indexOf('return $true');
  const fetchIdx = seg.indexOf('headRefOid');
  assert(fetchIdx > -1 && readyIdx > fetchIdx, 'READY is returned before the head is revalidated');
});
check('unreadable Codex inline comments fail closed', () => {
  const seg = ps1.split('function Get-CodexInlineFindings')[1].split('function Get-CodexVerdict')[0];
  assert(/Available = \$false/.test(seg), 'an API failure is indistinguishable from "no findings"');
  assert(/Available = \$true/.test(seg), 'no availability signal on success');
  const v = ps1.split('function Get-CodexVerdict')[1].split('function Wait-ForReviews')[0];
  assert(/-not \$inlineResult\.Available/.test(v), 'verdict ignores the availability signal');
  assert(/holding the verdict at PENDING/.test(v), 'unreadable inline set does not hold at PENDING');
});
check('Codex reviewer identity is exact, not a substring', () => {
  assert(/\$script:CODEX_BOT_LOGIN\s*=\s*"chatgpt-codex-connector\[bot\]"/.test(ps1),
    'expected Codex bot login is not pinned');
  // No substring matching on "codex" may survive for identity purposes.
  assert(!/-match '\(\?i\)codex'/.test(ps1), 'a substring identity match still exists');
  const uses = (ps1.match(/\$script:CODEX_BOT_LOGIN/g) || []).length;
  assert(uses >= 3, `bot login should gate reviews and inline comments, found ${uses} refs`);
});
check('severity set covers P0 and hyphenated must-fix', () => {
  const def = ps1.split('$script:CODEX_BLOCKING_PATTERN =')[1].split('\n')[0];
  assert(/P0/.test(def), 'P0 is not treated as blocking');
  assert(/must\[- \]fix/.test(def), 'hyphenated must-fix is not matched');
  assert(!/\bP3\b/.test(def.replace(/P0|P1|P2/g, '')), 'P3 is treated as blocking');
});
check('required checks must conclude success', () => {
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  assert(/\$_\.conclusion -eq "success"/.test(seg),
    'success is not required explicitly - a skipped/neutral/stale conclusion could satisfy the gate');
  assert(/no successful attempt; saw/.test(seg),
    'a check with no successful attempt at all is not reported');
  assert(/did not conclude success/.test(seg), 'non-success conclusions are not reported');
  assert(/Status = "FAIL"; Failing = \$notSuccessful/.test(seg), 'non-success does not fail the rollup');
});
check('an actively held lock is required, not merely a present file', () => {
  // A released lock usually retains its previous Allowed scope text, so continuing on
  // LOCKED: false would authorise writes from stale scope without acquiring ownership.
  const seg = ps1.split('function Test-WriteLock')[1].split('function Test-PathInLockScope')[0];
  assert(/if \(-not \$locked\)/.test(seg), 'a released lock does not stop the loop');
  assert(/A free lock is not write authorization/.test(seg), 'free lock is still treated as permission');
  assert(!/Write-Good "WRITE_LOCK is free"/.test(seg), 'still continues on a free lock');
});
check('claude cannot execute any file it is able to edit', () => {
  // Permission to run an editable script is permission to run whatever Claude just wrote,
  // including code that shells out to git commit/push. A self-commit would then vanish
  // from Get-ChangedFiles, which compares the working tree to the NEW HEAD.
  const seg = stripPs1Comments(ps1).split('function Get-ClaudeAllowedTools')[1].split('function ')[0];
  assert(!/node scripts\/ai\//.test(seg), 'allowedTools can execute editable scripts under scripts/ai/');
  assert(!/validate-worker\.mjs/.test(seg), 'allowedTools can execute an editable validator');
  assert(!/Bash\(node (?!--check)/.test(seg), 'allowedTools grants a non---check node invocation');
  // node --check only parses; it never executes.
  assert(/Bash\(node --check:\*\)/.test(seg), 'syntax checking was removed too');
});
check('a commit created during the implementation round is refused', () => {
  assert(/\$script:HeadBeforeRound/.test(ps1) && /\$headAfterRound/.test(ps1), 'HEAD is not sampled around the round');
  assert(/HEAD moved from/.test(ps1), 'a moved HEAD does not stop the loop');
  const body = stripPs1Comments(ps1);
  const beforeIdx = body.indexOf('$script:HeadBeforeRound = ');
  const roundIdx = body.indexOf('$claude = Invoke-ClaudeRound');
  const afterIdx = body.indexOf('$headAfterRound = ');
  assert(beforeIdx > -1 && beforeIdx < roundIdx && afterIdx > roundIdx,
    'HEAD must be sampled before AND after the round');
});
check('the reviewer runs from a trusted revision, not the PR head', () => {
  // The reviewer script is editable under the active lock. Running the head's copy would
  // let the change under review rewrite its own reviewer and post a forged current-SHA
  // ACCEPT under the Actions identity, which the bot+marker check would then admit.
  // Scoped to the REVIEWER job. The separate secretless selftest job legitimately checks
  // out the PR head - that is the revision whose safety is in question, and it holds no
  // credentials.
  const reviewJob = wf.split(/^\s{2}deepseek-review:/m)[1] || '';
  assert(/base\.ref|base\.sha/.test(reviewJob), 'reviewer job does not check out the base revision');
  assert(!/pull_request\.head\.sha \|\| format\('refs\/pull/.test(reviewJob),
    'reviewer job still checks out the PR head for execution');
  assert(/trusted/i.test(wf), 'the trust boundary is not documented in the workflow');
  // It still reviews the head: the SHA guard and the diff come from the API.
  assert(/--expect-sha/.test(wf), 'reviewer no longer pins the reviewed head');
});
check('a reused PR branch is reset to the advertised head', () => {
  // A local branch left ahead of the PR head would have its extra commits published by
  // the eventual push, while Assert-ChangesInLockScope only sees working-tree changes -
  // so out-of-scope commits would bypass the lock entirely.
  assert(/\$script:ExpectedPrHead/.test(ps1), 'the advertised PR head is never recorded');
  assert(/headRefName,headRefOid,state/.test(ps1), 'PR head oid is not fetched');
  const seg = ps1.split('function Initialize-Branch')[1].split('\nfunction ')[0];
  assert(/\$localHead -ne \$script:ExpectedPrHead/.test(seg), 'local tip is not compared to the PR head');
  assert(/reset", "--hard"/.test(seg), 'a divergent local branch is not reset');
  assert(/would publish commits this round never reviewed/.test(seg),
    'the consequence of a divergent branch is not stated or enforced');
});
check('the selftest runs in CI, isolated from the privileged reviewer', () => {
  // Otherwise every safety property here is only ever checked on a developer machine and
  // a regression can reach the repository unnoticed.
  assert(/ai-loop-selftest\.mjs/.test(wf), 'the selftest is never run by CI');
  assert(/setup-node/.test(wf), 'CI has no node runtime for the selftest');

  // It MUST be its own job. The selftest is lock-writable, so on a future PR it is
  // untrusted code; running it in the reviewer's job would let it overwrite the
  // checked-out reviewer or write $GITHUB_ENV before the reviewer executes with
  // DEEPSEEK_API_KEY and a write-capable token, forging a TRUST=trusted acceptance.
  assert(/^\s{2}loop-selftest:/m.test(wf), 'the selftest is not a separate job');
  const selftestJob = wf.split(/^\s{2}loop-selftest:/m)[1].split(/^\s{2}deepseek-review:/m)[0];
  const reviewJob = wf.split(/^\s{2}deepseek-review:/m)[1];

  // The untrusted job gets no secrets whatsoever.
  assert(!/secrets\./.test(selftestJob), 'the selftest job is exposed to secrets');
  assert(/permissions:\s*\n\s*contents: read/.test(selftestJob),
    'the selftest job does not drop to contents: read');
  assert(/head\.sha/.test(selftestJob), 'the selftest does not run against the PR head');
  assert(/Selftest missing/.test(selftestJob), 'a missing selftest is not treated as a failure');

  // And the privileged job must not execute PR-head code at all.
  assert(!/ai-loop-selftest/.test(reviewJob), 'the reviewer job still runs the PR-owned selftest');
});
check('the selftest is a required check', () =>
  assert(/"AI loop safety selftest"/.test(ps1),
    'the selftest can fail without blocking READY_TO_MERGE'));
check('the suite auditing a PR is the trusted base copy, not the PR head copy', () => {
  // This file is lock-writable, so on any PR its assertions are controlled by the change
  // under review. Running the head's own copy would let a malicious change rewrite its own
  // checks to pass - and it gates READY_TO_MERGE, so that would be a fail-open. The base
  // copy auditing the head's files keeps the assertions trusted and the subject untrusted,
  // exactly as the reviewer does.
  assert(/AI_LOOP_SELFTEST_ROOT/.test(read('scripts/ai/ai-loop-selftest.mjs')),
    'the suite cannot be pointed at an external tree');
  const job = wf.split(/^\s{2}loop-selftest:/m)[1].split(/^\s{2}deepseek-review:/m)[0];
  assert(/base\.ref/.test(job), 'the selftest job does not check out the trusted base');
  assert(/AI_LOOP_SELFTEST_ROOT:/.test(job), 'the job does not point the suite at the PR head');
  assert(/Untrusted selftest/.test(job),
    'the bootstrap fallback does not declare that its assertions are untrusted');
  // Still credential-free, and still not inside the privileged job.
  assert(!/secrets\./.test(job), 'the selftest job is exposed to secrets');
  // And the credential actions/checkout persists is dropped once fetching is done, so the
  // code about to run - which in bootstrap mode comes from the change under review - has
  // no token to pick up.
  assert(/--unset-all http\.https:\/\/github\.com\/\.extraheader/.test(job),
    'the persisted git credential is left available to the code the job runs');
  const unsetIdx = job.indexOf('--unset-all http');
  const runIdx = job.indexOf('node scripts/ai/ai-loop-selftest.mjs');
  assert(unsetIdx > -1 && unsetIdx < runIdx, 'the credential is dropped after the suite runs');
});
check('an absent remote branch does not disable the push guard', () => {
  // Get-RemoteBranchSha returns "" when the branch does not exist yet. A truthiness test
  // treats that as "skip", disabling the guard on exactly the common case - a freshly
  // created branch - so an unauthorised push could land with nothing to detect it.
  const pub = ps1.split('function Publish-Round')[1].split('\nfunction ')[0];
  assert(!/if \(\$script:RemoteBeforeRound\) \{/.test(pub), 'truthiness guard still present');
  // Stronger than distinguishing "" from $null: an UNAVAILABLE probe, before or after,
  // is itself a blocker. Skipping on a failed probe would leave an unauthorised push
  // undetected exactly when ls-remote is flaky.
  assert(/\$null -eq \$script:RemoteBeforeRound/.test(pub), 'a failed pre-round probe does not block');
  assert(/\$null -eq \$remoteNow/.test(pub), 'a failed post-round probe does not block');
  const blocks = (pub.match(/cannot be ruled out/g) || []).length;
  assert(blocks === 2, `both probe failures must block; found ${blocks} guard(s)`);
});
check('paginated GitHub reads survive multi-page responses - python side too', () => {
  // The identical defect existed in the reviewer: json.loads() over concatenated pages
  // raises "Extra data", the exception was read as "no existing comment", and every run
  // posted ANOTHER bot verdict instead of updating the single promised comment.
  const bad = py.match(/"--paginate",\s*\n?\s*"--jq", "\[/g) || [];
  assert(bad.length === 0, `${bad.length} python paginated call(s) still request an array per page`);
  assert(/def gh_json_lines/.test(py), 'python side has no line-delimited reader');
  const seg = py.split('def gh_json_lines')[1].split('\ndef ')[0];
  assert(/f"\.\[\] \| \{jq_object\}"/.test(seg), 'python reader does not emit one object per line');
  assert(/splitlines\(\)/.test(seg), 'python reader does not parse line by line');
  // upsert must use it, and must not silently treat a listing failure as "no comment".
  const up = py.split('def upsert_comment')[1].split('\ndef ')[0];
  assert(/gh_json_lines/.test(up), 'upsert_comment still uses the array reader');
  assert(/could not list existing PR comments/.test(up),
    'a failed listing is still silently treated as "no existing comment"');
});
check('paginated GitHub reads survive multi-page responses', () => {
  // gh --paginate emits ONE JSON document per page. With an array-producing --jq that
  // yields several concatenated arrays, and ConvertFrom-Json fuses them into a single
  // object whose scalar properties become space-joined lists - so `.login` came back as
  // every author at once, no author check could match, and every verdict read as PENDING.
  // The loop was silently unable to see ANY reviewer verdict.
  const bad = ps1.match(/--paginate", "--jq", "\[/g) || [];
  assert(bad.length === 0, `${bad.length} paginated call(s) still request a JSON array per page`);
  assert(/function Invoke-GhJsonLines/.test(ps1), 'no newline-delimited JSON reader');
  const helper = ps1.split('function Invoke-GhJsonLines')[1].split('\nfunction ')[0];
  assert(/"\.\[\] \| \$JqObject"/.test(helper), 'helper does not emit one object per line');
  assert(/StartsWith\("\{"\)/.test(helper), 'helper does not parse line by line');
  // Every reader that paginates must go through it.
  for (const fn of ['Get-DeepSeekVerdict', 'Get-CodexInlineFindings', 'Get-CodexVerdict']) {
    const seg = ps1.split(`function ${fn}`)[1].split('\nfunction ')[0];
    assert(/Invoke-GhJsonLines/.test(seg), `${fn} does not use the line-delimited reader`);
  }
});
check('a branch already carrying a committed workflow edit is refused', () => {
  // Assert-ChangesInLockScope only sees THIS round's changes. A reused PR whose head
  // already contains a workflow edit would pass it - and that PR-owned definition is what
  // GitHub runs for a same-repo pull_request, so it could post a same-SHA TRUST=trusted
  // verdict the controller would admit. The whole base..head range must be scanned.
  const seg = ps1.split('function Initialize-Branch')[1].split('\nfunction ')[0];
  // The COMMIT HISTORY is the primary check. A net tree diff is blind to an edit that was
  // later reverted, yet the branch still ran CI at that intermediate head with an
  // attacker-controlled workflow definition.
  assert(/"log", "--full-history", "--format=%H", "origin\/\$BaseBranch\.\.HEAD", "--", "\.github\/workflows"/.test(seg),
    'the commit history is never scanned for workflow changes, or omits --full-history');
  // Without --full-history, Git prunes TREESAME merge sides, so incorporating a malicious
  // workflow commit as the second parent of a `merge -s ours` hides it completely while
  // leaving it fully reachable in the range.
  assert(/--full-history/.test(seg), 'history scan omits --full-history and is evadable by a merge');
  assert(/\$offendingCommits/.test(seg), 'offending commits are not collected');
  assert(/even if the change was later reverted/.test(seg),
    'the guard does not state that a revert is still disqualifying');
  // Two-dot range: commits reachable from HEAD but not from base. Three dots would be the
  // symmetric difference and would implicate legitimate CI changes made on the base branch.
  assert(!/"log"[^\n]*BaseBranch\.\.\.HEAD/.test(seg),
    'history scan uses a symmetric-difference range, which would implicate base-branch commits');
  // The net tree diff is retained only as defence in depth.
  assert(/origin\/\$BaseBranch\.\.\.HEAD/.test(seg), 'base...head tree diff was dropped entirely');
  assert(/committedWorkflowEdits/.test(seg), 'committed workflow edits are not detected');
  assert(/already contains committed CI workflow change/.test(seg),
    'a pre-existing workflow edit does not block the run');
  // Either probe failing must block rather than silently skip.
  assert(/Refusing to run without that evidence/.test(seg),
    'an unavailable range diff disables the guard instead of blocking');
  const failClosed = (seg.match(/Refusing to run without that evidence/g) || []).length;
  assert(failClosed === 2, `both the history scan and the tree diff must fail closed; found ${failClosed}`);
  // History scan must run BEFORE the weaker tree diff, so the stronger verdict wins.
  const guardBody = stripPs1Comments(seg);
  assert(guardBody.indexOf('$historyScan') < guardBody.indexOf('$rangeDiff'),
    'the weaker tree diff is evaluated before the history scan');
  // And it must happen before any implementation round starts.
  const body = stripPs1Comments(ps1);
  assert(body.indexOf('committedWorkflowEdits') < body.indexOf('$claude = Invoke-ClaudeRound'),
    'the committed-workflow check runs after implementation has already begun');
});
check('the loop never authors a CI workflow change', () => {
  // For a same-repository pull_request event GitHub loads the workflow from the PR HEAD,
  // so a run able to edit its own workflow can replace the review step with one that posts
  // a forged current-SHA ACCEPT using the job's pull-requests: write token. Checking out a
  // trusted base pins the worktree but NOT the job definition, so the only control that
  // actually works is refusing to author the change.
  const seg = ps1.split('function Assert-ChangesInLockScope')[1].split('\nfunction ')[0];
  assert(/\^\\\.github\/workflows\//.test(seg), 'workflow paths are not detected');
  assert(/forge its own review verdict|forged/.test(seg), 'the reason is not documented');
  assert(/Stop-Loop -Status "BLOCKED"/.test(seg), 'a workflow edit does not block the round');
  // It must be checked before the general scope test, since a lock could list a workflow.
  const wfIdx = seg.indexOf('workflowEdits');
  const scopeIdx = seg.indexOf('$outside =');
  assert(wfIdx > -1 && wfIdx < scopeIdx, 'workflow guard does not precede the scope test');
});
check('a push is detected even if local HEAD is reset afterwards', () => {
  // A rewritten validator can commit, push with the controller's credentials, then reset
  // the local branch back to the saved SHA before returning success. Every local check
  // then passes while the unauthorised commit is already on the remote.
  assert(/function Get-RemoteBranchSha/.test(ps1), 'no remote tip probe');
  const helper = ps1.split('function Get-RemoteBranchSha')[1].split('\nfunction ')[0];
  assert(/ls-remote/.test(helper), 'remote tip is read from local refs rather than the server');
  assert(/\$script:RemoteBeforeRound = Get-RemoteBranchSha/.test(ps1), 'remote tip is not sampled pre-round');
  const pub = ps1.split('function Publish-Round')[1].split('\nfunction ')[0];
  assert(/\$script:RemoteBeforeRound/.test(pub), 'remote tip is not re-checked before staging');
  assert(/refusing to continue on a remote it did not author/.test(pub),
    'a moved remote does not block the round');
});
check('a bootstrap reviewer cannot vouch for the change that supplied it', () => {
  // On the PR that introduces the reviewer there is no trusted copy at base. Falling back
  // to the head copy silently would undo the whole trust boundary, so the fallback is
  // explicit and its verdict is not admissible as an acceptance.
  assert(/level=bootstrap/.test(wf), 'workflow has no bootstrap trust level');
  assert(/level=trusted/.test(wf), 'workflow never marks a review trusted');
  assert(/UNTRUSTED/.test(wf), 'bootstrap fallback is not flagged');
  assert(/--trust /.test(wf), 'trust level is not passed to the reviewer');
  assert(/"--trust", choices=\["trusted", "bootstrap"\]/.test(py), 'reviewer has no trust flag');
  assert(/f"TRUST=\{trust\}"/.test(py), 'trust level is not emitted in the verdict block');
  // Controller must refuse to count it as an acceptance.
  const seg = ps1.split('function Get-DeepSeekVerdict')[1].split('function Get-Codex')[0];
  assert(/TRUST/.test(seg), 'controller does not parse the trust level');
  assert(/\$trust -ne "trusted" -and \$verdict -eq "ACCEPT"/.test(seg),
    'an untrusted ACCEPT is still counted as an acceptance');
  assert(/\$verdict = "PENDING"/.test(seg), 'untrusted acceptance is not downgraded');
});
check('a force-pushed PR is refused, since its old history cannot be audited', () => {
  // A force-push makes the previous head UNREACHABLE, so no history scan can see it -
  // not even --full-history, which only walks the range it is given. The old workflow run
  // stays alive (the workflow deliberately does not cancel in progress), waits for the new
  // head, and can post a forged bot-authored acceptance for that SHA.
  assert(/function Assert-NoForcePush/.test(ps1), 'force-pushes are never detected');
  const seg = ps1.split('function Assert-NoForcePush')[1].split('\nfunction ')[0];
  assert(/head_ref_force_pushed/.test(seg), 'the timeline is not queried for force-push events');
  assert(/timeline/.test(seg), 'the PR timeline is never read');
  assert(/Stop-Loop -Status "BLOCKED"/.test(seg), 'a force-pushed PR does not block the run');
  // An unreadable timeline is itself a blocker: absence of evidence is not evidence.
  assert(/\$null -eq \$events/.test(seg), 'an unreadable timeline silently passes');
  assert(/without that evidence/.test(seg), 'an unreadable timeline is not treated as a blocker');
  // Checked when reusing a PR, and again before any verdict is trusted.
  const calls = (stripPs1Comments(ps1).match(/Assert-NoForcePush -PrNumber/g) || []).length;
  assert(calls >= 3, `force-push detection must run at branch resolution, before verdict trust, and at the readiness decision; found ${calls}`);
  // The decisive one is inside the readiness branch: a rewrite to a malicious workflow head
  // and back to the SAME sha during the polling window would satisfy the live-head
  // comparison, while the non-cancelling run posts a forged same-SHA verdict.
  const ready = ps1.split('if ($bothAccepted -and $shaFresh')[1].split('if ($checks.Status -eq "FAIL")')[0];
  assert(/Assert-NoForcePush -PrNumber/.test(ready),
    'force-push is not rechecked at the moment readiness is declared');
  // The timeline audit is a network round trip. An ordinary synchronize push landing
  // during it creates NO force-push event while the cached SHA still matches, so the head
  // must be re-read afterwards - the last thing checked before READY is the live head.
  assert(/\$liveShaBefore/.test(ready), 'the head is not captured before the audit for comparison');
  const auditIdx = ready.indexOf('Assert-NoForcePush -PrNumber');
  const rereadIdx = ready.indexOf('$liveAfter = Invoke-Gh');
  assert(rereadIdx > -1 && rereadIdx > auditIdx, 'the head is not re-read AFTER the timeline audit');
  assert(/PR head changed during the readiness audit/.test(ready),
    'a head change during the audit does not prevent readiness');
  // It must use the paginated NDJSON reader, not an array-per-page jq.
  assert(/Invoke-GhJsonLines -Path "repos\/\$Repo\/issues\/\$PrNumber\/timeline"/.test(seg),
    'timeline read does not use the multi-page-safe reader');
});
check('repository git hooks cannot influence controller git operations', () => {
  // Claude has Write/Edit, so a round could plant .git/hooks/pre-commit. Git excludes
  // .git/ from both `git diff` and `git ls-files --others`, so such a hook is invisible to
  // Get-ChangedFiles AND to both lock-scope assertions - yet the controller would EXECUTE
  // it through its own trusted git commit/push, under its own credentials.
  assert(/\$script:NO_HOOKS_PATH/.test(ps1), 'no hooks-path override is defined');
  const seg = ps1.split('function Invoke-Git')[1].split('\nfunction ')[0];
  assert(/core\.hooksPath=\$script:NO_HOOKS_PATH/.test(seg), 'git calls do not disable hooks');
  assert(/"-c", "core\.hooksPath/.test(seg), 'hooks-path is not passed as a git -c override');
  // It must apply to EVERY git invocation, not just commit/push.
  assert(/\$safeArgs = @\("-c", "core\.hooksPath=\$script:NO_HOOKS_PATH"\) \+ \$Arguments/.test(seg),
    'the hooks override is not prepended to every git invocation');
  // The placeholder must be a FILE, not an empty directory. An empty directory is
  // check-then-execute and therefore raceable: a detached helper can wait for git.exe to
  // start and write pre-commit into it after the check passed. Under a file, git resolves
  // <hooksPath>/pre-commit to something that cannot exist, and the path cannot be turned
  // into a hooks directory while it exists - an isolation boundary rather than a check.
  assert(/nohooks\.disabled/.test(ps1), 'the hooks placeholder is not a file path');
  assert(/Set-Content -Path \$script:NO_HOOKS_PATH/.test(seg),
    'the hooks placeholder is not created as a file');
  assert(!/New-Item -ItemType Directory -Force -Path \$script:NO_HOOKS_PATH/.test(seg),
    'the hooks placeholder is still created as a directory');
  // And if something replaced it with a directory, refuse.
  assert(/-PathType Container/.test(seg), 'the placeholder type is never re-verified');
  assert(/is a directory, not a file/.test(seg), 'a replaced placeholder does not block');
  // And a planted hook must be reported, not merely neutralised.
  assert(/function Assert-NoRepositoryHooks/.test(ps1), 'planted hooks are never detected');
  const det = ps1.split('function Assert-NoRepositoryHooks')[1].split('\nfunction ')[0];
  assert(/\*\.sample/.test(det), 'inert sample hooks are not excluded, so the check would always fire');
  assert(/Stop-Loop -Status "BLOCKED"/.test(det), 'a planted hook does not block the run');
  // Checked before the round and again before staging.
  const calls = (stripPs1Comments(ps1).match(/^\s*Assert-NoRepositoryHooks\s*$/gm) || []).length;
  assert(calls >= 2, `hook detection must run before the round and before staging; found ${calls}`);
});
check('a commit created during the TESTS is also refused', () => {
  // Closing Claude's direct execution is not enough: the controller itself runs
  // repo-resident validators that are writable under the lock.
  const seg = ps1.split('function Publish-Round')[1].split('function Sync-PullRequest')[0];
  assert(/\$script:HeadBeforeRound/.test(seg), 'HEAD is not re-checked before staging');
  assert(/refusing to stage on a history it did not author/.test(seg),
    'a commit created during the tests does not block staging');
  // The pre-round sample must be script-scoped so it survives into Publish-Round.
  assert(/\$script:HeadBeforeRound = \(Invoke-Git/.test(ps1), 'pre-round HEAD is not script-scoped');
});
check('the staged index is verified, not just the pre-staging working tree', () => {
  // `git add -A` is a separate step from the pre-staging scope check, so anything
  // appearing in between would be committed unexamined. Inspecting the INDEX removes the
  // window entirely: it is exactly the set about to become a commit.
  const pub = ps1.split('function Publish-Round')[1].split('\nfunction ')[0];
  assert(/"diff", "--cached", "--name-only"/.test(pub), 'the staged set is never inspected');
  const addIdx = pub.indexOf('"add", "-A"');
  const stagedIdx = pub.indexOf('"diff", "--cached", "--name-only"');
  assert(addIdx > -1 && stagedIdx > addIdx, 'the index is inspected before staging, not after');
  assert(/are staged for commit/.test(pub), 'out-of-scope staged files do not block');
  assert(/CI workflow file\(s\) are staged/.test(pub), 'staged workflow files do not block');
  const commitIdx = pub.indexOf('"commit", "-F"');
  assert(commitIdx > stagedIdx, 'the commit happens before the staged set is verified');
  // Even the index check is check-then-act: a detached helper can stage between the probe
  // and `git commit`. A COMMIT is immutable, so its own path list is the only inspection
  // that cannot be raced - and nothing has left the machine before the push.
  assert(/"show", "--name-only", "--format=", "HEAD"/.test(pub),
    'the created commit is never inspected');
  const showIdx = pub.indexOf('"show", "--name-only"');
  const pushIdx = pub.indexOf('"push", "origin"');
  assert(showIdx > commitIdx, 'the commit is inspected before it exists');
  assert(pushIdx > showIdx, 'the push happens before the commit is inspected');
  assert(/It has NOT been pushed/.test(pub),
    'a bad commit is not clearly reported as unpublished');
});
check('the NEWEST check attempt decides, not merely any success', () => {
  // "Any suite succeeded" was too weak: a check genuinely cancelled now would be waved
  // through by a stale success from earlier. Recency handles both cases with one rule.
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  assert(/\$newest = @\(\$matching \| Sort-Object/.test(seg), 'attempts are not ordered by recency');
  assert(/\$newest\.conclusion -ne "success"/.test(seg), 'the newest attempt is not required to succeed');
  assert(/latest attempt concluded/.test(seg), 'a failing latest attempt is not reported');
  // A bare "any success passes" must no longer exist on its own.
  assert(!/\} elseif \(\$succeed\.Count -gt 0\) \{/.test(seg),
    'a stale success can still satisfy the gate without being the newest attempt');
});
check('superseded attempts do not veto a later successful attempt', () => {
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  // Overlapping pull_request/workflow_dispatch triggers create separate check SUITES, so
  // a cancelled automatic run must not gate a later successful dispatched run.
  assert(/\$supersededConclusions/.test(seg), 'supersede signals are not distinguished');
  assert(/\$hardFailConclusions/.test(seg), 'genuine failures are not distinguished');
  assert(/cancelled/.test(seg) && /stale/.test(seg), 'cancelled/stale are not treated as superseded');
  assert(/\$succeed\.Count -gt 0/.test(seg), 'a successful attempt does not clear the check');
  // A genuine failure must still gate even when another suite went green.
  const hardIdx = seg.indexOf('$hard.Count -gt 0');
  const okIdx = seg.indexOf('$succeed.Count -gt 0');
  assert(hardIdx > -1 && hardIdx < okIdx, 'a real failure is not evaluated before a success');
});
check('superseded check attempts are collapsed before evaluation', () => {
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  // A cancelled earlier attempt must not report FAIL when a later attempt succeeded, and
  // an unrelated in-progress run must not hold the rollup at PENDING forever.
  const effIdx = seg.indexOf('$effective = @()');
  const reqIdx = seg.indexOf('foreach ($required in $script:REQUIRED_CHECKS)');
  assert(effIdx > -1 && reqIdx > effIdx, 'required-check evaluation runs before attempts are collapsed');
  assert(!/foreach \(\$run in \$runs\)/.test(seg), 'still scans every historical run first');
  assert(/\$\(\$_\.name\)\|\$\(\$_\.suite\)/.test(seg), 'attempt identity is not (name, suite)');
});
check('non-required failing checks are reported but do not gate', () => {
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  assert(/OtherFailing/.test(seg), 'non-required failures are not surfaced at all');
  assert(/not gating/.test(seg), 'non-required failures are not distinguished from gating ones');
  // The gate itself must consider only the required set.
  assert(/REQUIRED_CHECKS -notcontains/.test(seg), 'non-required checks are not separated out');
  // EVERY return path must carry them, including PENDING and FAIL - the contract promises
  // they stay visible, and logging alone does not reach the summary.
  const returns = seg.match(/return \[pscustomobject\]@\{ Status = "(PASS|FAIL|PENDING)"[^}]*\}/g) || [];
  assert(returns.length >= 3, `expected PASS/FAIL/PENDING returns, found ${returns.length}`);
  for (const r of returns) assert(/OtherFailing/.test(r), `return path omits OtherFailing: ${r}`);
  // And they must actually reach the state and the printed summary.
  assert(/checks_other_failing/.test(ps1), 'non-required failures never reach loop state');
  assert(/CHECKS_OTHER_FAILING=/.test(ps1), 'non-required failures never reach the summary');
});
check('only the latest attempt of a required check counts', () => {
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  // An old green run must not mask a rerun that concluded neutral/skipped/stale.
  assert(/Sort-Object[\s\S]{0,120}-Descending/.test(seg), 'attempts are not ordered');
  assert(/started_at/.test(seg), 'attempt recency is not considered');
  assert(/\$effective \+= @\(\$group\.Group \| Sort-Object/.test(seg),
    'the latest attempt per group is not the one retained');
  assert(/\$matching = @\(\$effective \| Where-Object/.test(seg),
    'required checks are evaluated against raw runs rather than the collapsed set');
  assert(!/\$ok\.Count -eq 0/.test(seg), 'still accepts any historical successful attempt');
  assert(/started_at, id/.test(ps1), 'check-run query does not fetch attempt ordering fields');
});
check('an unparsed lock scope fails closed', () => {
  // Empty AllowedPaths previously meant "allow everything", silently disabling the guard
  // if the Allowed scope section were renamed, malformed or missing.
  const seg = ps1.split('function Test-PathInLockScope')[1].split('function Assert-ChangesInLockScope')[0];
  assert(/AllowedPaths\)\.Count -eq 0\) \{ return \$false \}/.test(seg),
    'empty scope still authorises every path');
  assert(/declares no enumerated allowed paths/.test(ps1), 'empty scope is not a hard blocker');
  assert(/Stop-Loop -Status "BLOCKED" -Reason "WRITE_LOCK declares no enumerated/.test(ps1),
    'empty scope does not stop the loop');
});
check('all same-head Codex reviews are aggregated', () => {
  const seg = ps1.split('function Get-CodexVerdict')[1].split('function Wait-ForReviews')[0];
  assert(/\$sameHead = @\(\$reviews \| Where-Object/.test(seg), 'reviews are not collected as a set');
  // No early return on the first matching review.
  assert(!/foreach \(\$rev in \$reviews\)/.test(seg), 'still iterates and returns on first match');
  assert(/\$blockers\.Count -gt 0/.test(seg), 'rejection does not take precedence over the set');
});
check('every persisted state key is declared by the schema', () => {
  // The schema is additionalProperties:false, so any state field the controller emits but
  // the schema does not declare invalidates every persisted state file. Derive the key set
  // from the controller itself so adding a field without updating the schema fails here.
  const block = ps1.split('$script:State = [ordered]@{')[1].split('\n}')[0];
  const keys = [...block.matchAll(/^\s{4}([a-z_]+)\s*=/gm)].map((m) => m[1]);
  assert(keys.length >= 15, `expected the full state key set, parsed ${keys.length}`);
  // Keys deliberately re-nested during serialisation rather than emitted at top level.
  const renested = new Set(['checks_other_failing']);
  const declared = new Set(Object.keys(schema.properties));
  const undeclared = keys.filter((k) => !declared.has(k) && !renested.has(k));
  assert(undeclared.length === 0, `state keys missing from the schema: ${undeclared.join(', ')}`);
  // Anything re-nested must actually be removed before serialisation.
  for (const k of renested) {
    assert(new RegExp(`Remove\\("${k}"\\)`).test(ps1), `${k} is re-nested but never removed from the top level`);
  }
});
check('blocking findings are serialised in the schema shape', () => {
  const seg = ps1.split('function Write-Summary')[1];
  assert(/\$serialisable\["blocking_findings"\]/.test(seg), 'blocking_findings are copied verbatim as strings');
  assert(/source = \$source; summary = \$text/.test(seg), 'findings are not objects with source and summary');
  const item = schema.properties.blocking_findings.items;
  assert(item.required.includes('source') && item.required.includes('summary'),
    'schema does not require source and summary');
  for (const s of ['CODEX', 'DEEPSEEK', 'TESTS', 'CHECKS', 'CONTROLLER']) {
    assert(item.properties.source.enum.includes(s), `schema source enum missing ${s}`);
    assert(seg.includes(`"${s}"`), `controller never emits source ${s}`);
  }
});
check('reviewer only updates its own comments', () => {
  // Marker-only matching also matches comments that merely QUOTE the marker, so the
  // reviewer would overwrite a human's comment and strand its verdict under a non-bot
  // author - which the controller must then ignore, stalling the loop at PENDING.
  const seg = py.split('def upsert_comment')[1].split('def emit_outputs')[0];
  assert(/BOT_LOGIN/.test(seg), 'comment author is not checked before updating');
  assert(/login: \.user\.login/.test(seg), 'comment author is not even fetched');
  const loginIdx = seg.indexOf('c.get("login") != BOT_LOGIN');
  const markerIdx = seg.indexOf('COMMENT_MARKER in');
  assert(loginIdx > -1 && loginIdx < markerIdx, 'author check does not gate the marker match');
});
check('Codex severity set is identical inline and in the summary', () => {
  // An asymmetric threshold lets the same defect block in one place and pass in the other.
  assert(/\$script:CODEX_BLOCKING_PATTERN\s*=/.test(ps1), 'no single blocking-severity definition');
  const uses = (ps1.match(/\$script:CODEX_BLOCKING_PATTERN/g) || []).length;
  assert(uses >= 3, `severity pattern should be defined once and used everywhere, found ${uses} refs`);
  // No hand-rolled severity regex may survive alongside it.
  const strays = (ps1.match(/-match '\(\?i\)\\b\(P1/g) || []).length;
  assert(strays === 0, 'a duplicate inline severity regex still exists');
  // P3 is informational and must not appear in the blocking set.
  const def = ps1.split('$script:CODEX_BLOCKING_PATTERN =')[1].split('\n')[0];
  assert(!/P3/.test(def), 'P3 is treated as blocking');
  assert(/P1/.test(def) && /P2/.test(def), 'P1/P2 are not treated as blocking');
});
check('no stray control characters in the controller', () => {
  // A literal 0x08 once replaced a \b escape here and silently broke the regex.
  const ctrl = ps1.match(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g) || [];
  assert(ctrl.length === 0, `found ${ctrl.length} control character(s) in ai-loop.ps1`);
});
check('workflow has no duplicate sibling keys', () => {
  // PyYAML silently keeps the last of a duplicated key, but GitHub Actions rejects the
  // workflow at startup - producing a failed run with zero jobs and no log. A plain
  // "does it parse" check cannot catch this, so scan sibling keys directly.
  const lines = wf.split('\n');
  const stack = new Map(); // indent -> Set of keys seen in the current block
  const dupes = [];
  let lastIndent = -1;
  lines.forEach((raw, i) => {
    if (/^\s*#/.test(raw) || !raw.trim()) return;
    const m = raw.match(/^(\s*)(-\s+)?([A-Za-z_][\w-]*)\s*:(\s|$)/);
    if (!m) return;
    const indent = m[1].length + (m[2] ? m[2].length : 0);
    const key = m[3];
    if (m[2]) {
      // A new list item starts a fresh mapping at this level and below.
      for (const k of [...stack.keys()]) if (k >= indent) stack.delete(k);
    } else if (indent < lastIndent) {
      // A dedent closes deeper blocks only. Returning to `indent` re-enters the SAME
      // mapping, so its recorded keys must survive - otherwise a duplicate that straddles
      // a nested block (the exact `env:` bug) goes undetected.
      for (const k of [...stack.keys()]) if (k > indent) stack.delete(k);
    }
    if (!stack.has(indent)) stack.set(indent, new Set());
    const seen = stack.get(indent);
    if (seen.has(key)) dupes.push(`line ${i + 1}: duplicate key "${key}"`);
    seen.add(key);
    lastIndent = indent;
  });
  assert(dupes.length === 0, dupes.join('; '));
});
check('workflow always arms the stale-head guard', () => {
  assert(/--expect-sha/.test(wf), 'no stale-head guard');
  // workflow_dispatch has no pull_request payload, so the SHA must be resolved from the API.
  assert(/head\.sha/.test(wf), 'head sha is not resolved for workflow_dispatch');
  assert(/refusing to review without the stale-head guard/.test(wf),
    'workflow proceeds even when the head sha cannot be resolved');
});
check('reviewer stages its comment body safely', () => {
  assert(/os\.makedirs\(tmp_dir, exist_ok=True\)/.test(py), 'temp dir is assumed to exist');
  assert(/could not stage the comment body/.test(py), 'staging failure is not classified');
});
check('Codex inline findings are treated as blocking', () => {
  assert(/function Get-CodexInlineFindings/.test(ps1), 'inline review comments are never read');
  const seg = ps1.split('function Get-CodexInlineFindings')[1].split('function Wait-ForReviews')[0];
  assert(/pulls\/\$\(\$script:State\.pr_number\)\/comments/.test(seg), 'does not query inline comments');
  assert(/\$script:CODEX_BLOCKING_PATTERN/.test(seg),
    'inline scan does not use the shared blocking-severity definition');
  assert(/\$blockers\.Count -gt 0/.test(seg), 'inline findings do not override the review state');
  assert(/original_commit_id/.test(seg), 'inline findings are not pinned to a commit');
});
check('check rollup requires named checks to actually report', () => {
  assert(/\$script:REQUIRED_CHECKS\s*=\s*@\(/.test(ps1), 'no required-check list');
  const seg = ps1.split('function Get-CheckRollup')[1].split('function Get-DeepSeekVerdict')[0];
  assert(/foreach \(\$required in \$script:REQUIRED_CHECKS\)/.test(seg), 'required checks are not verified present');
  assert(/absent\.Count -gt 0/.test(seg), 'absent required checks do not downgrade the rollup');
  assert(/Status = "PENDING"[\s\S]{0,80}\}\s*\n\s*return \[pscustomobject\]@\{ Status = "PASS"/.test(seg)
    || /absent[\s\S]{0,200}PENDING/.test(seg), 'absent required checks still yield PASS');
});
check('unverified Claude round fails closed', () => {
  const seg = ps1.split('$claude = Invoke-ClaudeRound')[1].split('$testsPass = ')[0];
  assert(/SafetyInvariants -ne "PASS"/.test(seg),
    'only an explicit FAIL is caught; UNKNOWN would pass through as safe');
  assert(/@\(\$claude\.Blockers\)\.Count -gt 0/.test(seg),
    'blockers are ignored unless STATUS=BLOCKED');
  assert(/"IMPLEMENTED", "NO_CHANGE_NEEDED"/.test(seg), 'an unknown STATUS is accepted');
});
check('persisted state matches the schema shape', () => {
  const seg = ps1.split('function Write-Summary')[1];
  assert(/\$serialisable\["tests"\]\s*=\s*\[ordered\]@\{/.test(seg), 'tests is not serialised as an object');
  assert(/\$serialisable\["checks"\]\s*=\s*\[ordered\]@\{/.test(seg), 'checks is not serialised as an object');
  assert(/status\s*=\s*\$script:State\.checks/.test(seg), 'checks.status is not serialised');
  // Schema is additionalProperties:false, so no state key may be emitted that it does not
  // declare. Non-required failures belong INSIDE checks, not as a new top-level field.
  assert(/\$serialisable\.Remove\("checks_other_failing"\)/.test(seg),
    'a top-level key not declared by the schema is still emitted');
  assert(schema.properties.checks.properties.other_failing, 'schema does not declare checks.other_failing');
  assert(schema.additionalProperties === false, 'schema no longer forbids undeclared properties');
  // Schema agrees these are objects with a status property.
  assert(schema.properties.tests.type === 'object', 'schema tests is not an object');
  assert(schema.properties.checks.type === 'object', 'schema checks is not an object');
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
// =====================================================================================
// 17. BEHAVIOURAL: the CI-workflow history guard, exercised against real git repositories.
//
// The controller decides this with two git commands. Asserting they appear in the source
// proves only that they are written down, so these tests build throwaway repositories and
// run the exact commands, checking the verdict each one produces. That is what catches a
// wrong revision range or a net-diff blind spot.
// =====================================================================================
function gitAvailable() {
  try {
    execFileSync('git', ['--version'], { stdio: 'ignore' });
    return true;
  } catch { return false; }
}

function git(cwd, args) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}

/** Build a repo with a `main` base and a `feature` branch, then apply `commits`. */
function buildRepo(commits) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-loop-guard-'));
  git(dir, ['init', '-q', '-b', 'main', '.']);
  git(dir, ['config', 'user.email', 'selftest@example.invalid']);
  git(dir, ['config', 'user.name', 'selftest']);
  git(dir, ['config', 'commit.gpgsign', 'false']);
  fs.mkdirSync(path.join(dir, '.github', 'workflows'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'src'), { recursive: true });
  fs.writeFileSync(path.join(dir, '.github/workflows/ci.yml'), 'name: ci\n');
  fs.writeFileSync(path.join(dir, 'src/app.txt'), 'base\n');
  git(dir, ['add', '-A']);
  git(dir, ['commit', '-qm', 'base']);
  // `origin/main` is what the controller compares against; a local alias stands in for it.
  git(dir, ['update-ref', 'refs/remotes/origin/main', 'refs/heads/main']);
  git(dir, ['checkout', '-qb', 'feature']);
  for (const c of commits) { c(dir); }
  return dir;
}

const writeFile = (rel, body) => (dir) => {
  const target = path.join(dir, rel);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, body);
  git(dir, ['add', '-A']);
  git(dir, ['commit', '-qm', `write ${rel}`]);
};
const restoreFromBase = (rel) => (dir) => {
  git(dir, ['checkout', '-q', 'origin/main', '--', rel]);
  git(dir, ['add', '-A']);
  git(dir, ['commit', '-qm', `revert ${rel}`]);
};

/** The controller's PRIMARY check: any commit in base..HEAD touching workflows.
 *  Mirrors the controller exactly, --full-history included: without it Git prunes
 *  TREESAME merge sides and a `merge -s ours` hides the offending commit entirely. */
function historyGuardBlocks(dir) {
  const out = git(dir, ['log', '--full-history', '--format=%H', 'origin/main..HEAD', '--', '.github/workflows']);
  return out.split('\n').filter((l) => l.trim()).length > 0;
}

/** The pre-fix probe, retained ONLY so a test can prove it was genuinely blind. */
function simplifiedHistoryBlocks(dir) {
  const out = git(dir, ['log', '--format=%H', 'origin/main..HEAD', '--', '.github/workflows']);
  return out.split('\n').filter((l) => l.trim()).length > 0;
}

/** The controller's SECONDARY check: the net tree diff. Kept only as defence in depth. */
function treeDiffBlocks(dir) {
  const out = git(dir, ['diff', '--name-only', 'origin/main...HEAD']);
  return out.split('\n').some((l) => l.trim().startsWith('.github/workflows/'));
}

if (!gitAvailable()) {
  check('CI-workflow history guard behaviour (git unavailable)', () => {
    throw new Error('git is required to exercise the workflow history guard');
  });
} else {
  check('BEHAVIOUR: workflow edited then reverted is still BLOCKED', () => {
    // The case a net tree diff cannot see. The branch ran CI at the intermediate head with
    // an attacker-controlled workflow, and those check runs stay attached to the PR.
    const dir = buildRepo([
      writeFile('.github/workflows/ci.yml', 'name: ci\n# tampered\n'),
      restoreFromBase('.github/workflows/ci.yml'),
      writeFile('src/app.txt', 'more work\n'),
    ]);
    assert(historyGuardBlocks(dir), 'history guard missed a reverted workflow edit');
    // Proves the guard is not redundant: the old net-diff check is blind here.
    assert(!treeDiffBlocks(dir),
      'tree diff unexpectedly saw the revert - the history guard would be redundant');
  });

  check('BEHAVIOUR: workflow edited in any historical commit is BLOCKED', () => {
    const dir = buildRepo([
      writeFile('src/app.txt', 'ordinary\n'),
      writeFile('.github/workflows/ci.yml', 'name: ci\n# tampered\n'),
      writeFile('src/app.txt', 'more ordinary\n'),
    ]);
    assert(historyGuardBlocks(dir), 'history guard missed a mid-history workflow edit');
  });

  check('BEHAVIOUR: a newly ADDED workflow file is BLOCKED', () => {
    // Adding a brand new workflow is as dangerous as editing one; GitHub will run it.
    const dir = buildRepo([writeFile('.github/workflows/evil.yml', 'name: evil\n')]);
    assert(historyGuardBlocks(dir), 'history guard missed an added workflow file');
  });

  check('BEHAVIOUR: a workflow commit hidden by `merge -s ours` is still BLOCKED', () => {
    // Git's default path-history simplification prunes TREESAME sides of a merge. Carrying
    // the malicious commit in as the SECOND PARENT of a `merge -s ours` therefore leaves it
    // fully reachable in the range while the simplified log prints nothing and the net tree
    // diff is empty - and the workflow run it started can still be alive, waiting for the
    // clean head to post a forged same-SHA verdict.
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-loop-guard-merge-'));
    git(dir, ['init', '-q', '-b', 'main', '.']);
    git(dir, ['config', 'user.email', 'selftest@example.invalid']);
    git(dir, ['config', 'user.name', 'selftest']);
    git(dir, ['config', 'commit.gpgsign', 'false']);
    fs.mkdirSync(path.join(dir, '.github', 'workflows'), { recursive: true });
    fs.mkdirSync(path.join(dir, 'src'), { recursive: true });
    fs.writeFileSync(path.join(dir, '.github/workflows/ci.yml'), 'name: ci\n');
    fs.writeFileSync(path.join(dir, 'src/app.txt'), 'base\n');
    git(dir, ['add', '-A']);
    git(dir, ['commit', '-qm', 'base']);
    git(dir, ['update-ref', 'refs/remotes/origin/main', 'refs/heads/main']);

    // A side branch carrying the malicious workflow edit.
    git(dir, ['checkout', '-qb', 'evil']);
    fs.writeFileSync(path.join(dir, '.github/workflows/ci.yml'), 'name: ci\n# tampered\n');
    git(dir, ['add', '-A']);
    git(dir, ['commit', '-qm', 'malicious workflow edit']);
    const evilSha = git(dir, ['rev-parse', 'evil']).trim();

    // The feature branch absorbs it with -s ours, so HEAD's tree is clean.
    git(dir, ['checkout', '-qb', 'feature', 'main']);
    fs.writeFileSync(path.join(dir, 'src/app.txt', ), 'work\n');
    git(dir, ['add', '-A']);
    git(dir, ['commit', '-qm', 'ordinary work']);
    git(dir, ['merge', '-s', 'ours', '-q', '--no-edit', 'evil']);

    // The commit really is in the range, and HEAD's workflow really is clean.
    const reachable = git(dir, ['rev-list', 'origin/main..HEAD']).split('\n').map((s) => s.trim());
    assert(reachable.includes(evilSha), 'test setup wrong: the malicious commit is not reachable');
    assert(!git(dir, ['show', 'HEAD:.github/workflows/ci.yml']).includes('tampered'),
      'test setup wrong: HEAD workflow should look clean');

    // Both pre-fix probes are blind; only --full-history sees it.
    assert(!treeDiffBlocks(dir), 'tree diff unexpectedly caught it - scenario is not the blind spot');
    assert(!simplifiedHistoryBlocks(dir),
      'simplified log unexpectedly caught it - scenario is not the blind spot');
    assert(historyGuardBlocks(dir), 'the --full-history guard missed a workflow commit hidden behind merge -s ours');
  });

  check('BEHAVIOUR: no workflow touched anywhere in history is ALLOWED', () => {
    const dir = buildRepo([
      writeFile('src/app.txt', 'work\n'),
      writeFile('src/other.txt', 'more\n'),
    ]);
    assert(!historyGuardBlocks(dir), 'history guard blocked a branch that never touched workflows');
    assert(!treeDiffBlocks(dir), 'tree diff blocked a branch that never touched workflows');
  });

  check('BEHAVIOUR: ordinary non-workflow commits are ALLOWED', () => {
    const dir = buildRepo([
      writeFile('scripts/ai-note.txt', 'in-scope edit\n'),
      writeFile('src/app.txt', 'refactor\n'),
      writeFile('src/app.txt', 'refactor again\n'),
    ]);
    assert(!historyGuardBlocks(dir), 'history guard blocked ordinary work');
    assert(!treeDiffBlocks(dir), 'tree diff blocked ordinary work');
  });

  check('BEHAVIOUR: a base-branch workflow change does not implicate the feature branch', () => {
    // Only commits reachable from HEAD but not from base may disqualify it, otherwise every
    // branch cut after a legitimate CI change would be permanently unusable.
    const dir = buildRepo([writeFile('src/app.txt', 'work\n')]);
    git(dir, ['checkout', '-q', 'main']);
    fs.writeFileSync(path.join(dir, '.github/workflows/ci.yml'), 'name: ci\n# merged by a human\n');
    git(dir, ['add', '-A']);
    git(dir, ['commit', '-qm', 'human CI change on base']);
    git(dir, ['update-ref', 'refs/remotes/origin/main', 'refs/heads/main']);
    git(dir, ['checkout', '-q', 'feature']);
    assert(!historyGuardBlocks(dir), 'a workflow change on the BASE branch wrongly blocked the feature branch');
  });
}

console.log('');
if (failures.length) {
  console.log(`AI_LOOP_SELFTEST FAIL  ${passed} passed, ${failures.length} failed`);
  for (const f of failures) console.log(`  - ${f.name}: ${f.message}`);
  process.exit(1);
}
console.log(`AI_LOOP_SELFTEST PASS  ${passed}/${passed} checks`);
process.exit(0);
