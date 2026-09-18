// Node-only tests for cloudflare-worker/project-resolution.js (Task 1).
// No new dependencies. Run with: node test-project-resolution.mjs

import assert from "node:assert/strict";
import { resolveProjectId, normalizeProjectId } from "./project-resolution.js";

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`not ok - ${name}`);
    console.error(err && err.stack ? err.stack : err);
    process.exitCode = 1;
  }
}

// --- explicit wins ---------------------------------------------------------

test("explicit project_id wins when valid", () => {
  const result = resolveProjectId(
    { project_id: "proj-alpha" },
    { approved: true, project_id: "proj-client" },
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, "proj-alpha");
});

test("explicit projectId (camelCase) wins when valid", () => {
  const result = resolveProjectId(
    { projectId: "proj-alpha" },
    null,
    null
  );
  assert.equal(result, "proj-alpha");
});

test("explicit wins even when defaults are absent", () => {
  assert.equal(resolveProjectId({ project_id: "p1" }, null, null), "p1");
});

// --- approved client default ----------------------------------------------

test("approved client default used when no explicit id", () => {
  const result = resolveProjectId(
    {},
    { approved: true, project_id: "proj-client" },
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, "proj-client");
});

test("client default takes precedence over stored default", () => {
  const result = resolveProjectId(
    null,
    { approved: true, project_id: "proj-client" },
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, "proj-client");
});

// --- stored default --------------------------------------------------------

test("stored approved default used when no explicit id and no client default", () => {
  const result = resolveProjectId(
    {},
    null,
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, "proj-stored");
});

test("stored approved default used when client default is unapproved", () => {
  const result = resolveProjectId(
    {},
    { approved: false, project_id: "proj-client" },
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, "proj-stored");
});

// --- ambiguity fails closed ------------------------------------------------

test("conflicting explicit identifiers fail closed", () => {
  const result = resolveProjectId(
    { project_id: "proj-a", projectId: "proj-b" },
    { approved: true, project_id: "proj-client" },
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, null);
});

test("matching explicit identifiers are not ambiguous", () => {
  const result = resolveProjectId(
    { project_id: "proj-a", projectId: "proj-a" },
    null,
    null
  );
  assert.equal(result, "proj-a");
});

// --- malformed inputs ------------------------------------------------------

test("empty explicit project_id fails closed", () => {
  assert.equal(resolveProjectId({ project_id: "" }, null, null), null);
});

test("non-string explicit project_id fails closed", () => {
  assert.equal(resolveProjectId({ project_id: 123 }, null, null), null);
  assert.equal(resolveProjectId({ project_id: null }, null, null), null);
  assert.equal(resolveProjectId({ project_id: {} }, null, null), null);
  assert.equal(resolveProjectId({ project_id: [] }, null, null), null);
});

test("whitespace-padded explicit project_id fails closed", () => {
  assert.equal(resolveProjectId({ project_id: " proj-a " }, null, null), null);
});

test("overlong explicit project_id fails closed", () => {
  const long = "a".repeat(129);
  assert.equal(resolveProjectId({ project_id: long }, null, null), null);
});

test("malformed explicit id does not fall through to defaults", () => {
  const result = resolveProjectId(
    { project_id: "" },
    { approved: true, project_id: "proj-client" },
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, null);
});

test("unapproved client default is ignored", () => {
  const result = resolveProjectId(
    {},
    { approved: false, project_id: "proj-client" },
    null
  );
  assert.equal(result, null);
});

test("client default without approved flag is ignored", () => {
  const result = resolveProjectId({}, { project_id: "proj-client" }, null);
  assert.equal(result, null);
});

test("malformed client default is ignored", () => {
  const result = resolveProjectId(
    {},
    { approved: true, project_id: "" },
    { approved: true, project_id: "proj-stored" }
  );
  assert.equal(result, "proj-stored");
});

test("malformed stored default returns null", () => {
  assert.equal(
    resolveProjectId({}, null, { approved: true, project_id: 42 }),
    null
  );
  assert.equal(
    resolveProjectId({}, null, { approved: true, project_id: "" }),
    null
  );
});

test("unapproved stored default returns null", () => {
  assert.equal(
    resolveProjectId({}, null, { approved: false, project_id: "proj-stored" }),
    null
  );
  assert.equal(
    resolveProjectId({}, null, { project_id: "proj-stored" }),
    null
  );
});

// --- no-guess behavior -----------------------------------------------------

test("no inputs at all returns null (never guesses)", () => {
  assert.equal(resolveProjectId(null, null, null), null);
  assert.equal(resolveProjectId(undefined, undefined, undefined), null);
  assert.equal(resolveProjectId({}, {}, {}), null);
});

test("non-object inputs return null", () => {
  assert.equal(resolveProjectId("proj-a", null, null), null);
  assert.equal(resolveProjectId(42, null, null), null);
  assert.equal(resolveProjectId([], null, null), null);
});

test("does not read unrelated fields as project ids", () => {
  const result = resolveProjectId(
    { project: "proj-a", id: "proj-b" },
    null,
    null
  );
  assert.equal(result, null);
});

// --- normalizeProjectId unit checks ---------------------------------------

test("normalizeProjectId accepts valid ids", () => {
  assert.equal(normalizeProjectId("proj-a"), "proj-a");
  assert.equal(normalizeProjectId("A1._:-x"), "A1._:-x");
});

test("normalizeProjectId rejects invalid ids", () => {
  assert.equal(normalizeProjectId(""), null);
  assert.equal(normalizeProjectId(" proj-a"), null);
  assert.equal(normalizeProjectId("proj a"), null);
  assert.equal(normalizeProjectId("-proj"), null);
  assert.equal(normalizeProjectId(123), null);
  assert.equal(normalizeProjectId(null), null);
  assert.equal(normalizeProjectId(undefined), null);
  assert.equal(normalizeProjectId({}), null);
});

// --- determinism -----------------------------------------------------------

test("resolution is deterministic across repeated calls", () => {
  const req = { project_id: "proj-a" };
  const first = resolveProjectId(req, null, null);
  for (let i = 0; i < 100; i += 1) {
    assert.equal(resolveProjectId(req, null, null), first);
  }
});

console.log(`\n${passed} tests passed`);
