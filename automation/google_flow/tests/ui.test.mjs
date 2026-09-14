import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const base = new URL('../chrome_extension/', import.meta.url);

test('popup exposes persistent autopilot, calibration, preflight and pause controls', async () => {
  const html = await readFile(new URL('popup.html', base), 'utf8');
  for (const id of ['autopilotToggle','commandBusUrl','pollMinutes','promptSelector','generateSelector','runPreflight','pollNow','pauseBtn','resumeBtn','stopBtn','exportLog','clearInflight','status']) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
});

test('popup implementation does not collect credential fields', async () => {
  const html = await readFile(new URL('popup.html', base), 'utf8');
  assert.equal(/type=["']password["']/i.test(html), false);
  assert.equal(/cookie|2fa|refresh token|github pat/i.test(html), false);
});
