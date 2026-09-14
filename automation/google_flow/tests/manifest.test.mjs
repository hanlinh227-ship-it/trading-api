import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const manifestPath = new URL('../chrome_extension/manifest.json', import.meta.url);

async function manifest() {
  return JSON.parse(await readFile(manifestPath, 'utf8'));
}

test('uses Manifest V3 with persistent alarm capability', async () => {
  const m = await manifest();
  assert.equal(m.manifest_version, 3);
  assert.equal(m.version, '0.3.0');
  assert.ok(m.permissions.includes('storage'));
  assert.ok(m.permissions.includes('tabs'));
  assert.ok(m.permissions.includes('alarms'));
});

test('does not request all_urls or broad arbitrary website access', async () => {
  const m = await manifest();
  const all = JSON.stringify(m);
  assert.equal(all.includes('<all_urls>'), false);
  assert.deepEqual(m.host_permissions.sort(), [
    'https://flow.google.com/*',
    'https://labs.google/fx/tools/flow/*',
    'https://raw.githubusercontent.com/*'
  ].sort());
});

test('loads content scripts only on Flow origins', async () => {
  const m = await manifest();
  assert.equal(m.content_scripts.length, 1);
  assert.deepEqual(m.content_scripts[0].matches.sort(), [
    'https://flow.google.com/*',
    'https://labs.google/fx/tools/flow/*'
  ].sort());
});
