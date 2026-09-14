import test from 'node:test';
import assert from 'node:assert/strict';
import { validateQueue, isAllowedFlowUrl } from '../chrome_extension/lib/queue.js';

const NOW = Date.parse('2026-09-14T06:00:00Z');

function validCommand(overrides = {}) {
  return {
    command_id: 'flow-20260914-scene24-001',
    created_at: '2026-09-14T05:00:00Z',
    not_before: null,
    expires_at: '2026-09-15T05:00:00Z',
    action: 'render',
    project_url: 'https://labs.google/fx/tools/flow/project-123',
    scene: 24,
    prompt: 'animate gently',
    duration_seconds: 8,
    aspect_ratio: '16:9',
    start_image: { mode: 'current' },
    end_image: { mode: 'none' },
    output_filename: 'Scene_24.mp4',
    retry: { max_attempts: 1 },
    ...overrides,
  };
}

function queue(commands = [validCommand()]) {
  return {
    schema_version: 1,
    updated_at: '2026-09-14T05:00:00Z',
    commands,
  };
}

test('accepts a valid bounded render queue', () => {
  const result = validateQueue(queue(), NOW);
  assert.equal(result.ok, true);
  assert.equal(result.errors.length, 0);
  assert.equal(result.commands.length, 1);
  assert.equal(result.commands[0].scene, 24);
});

test('rejects expired commands', () => {
  const result = validateQueue(queue([validCommand({ expires_at: '2026-09-14T05:30:00Z' })]), NOW);
  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /expired/i);
});

test('rejects unsupported actions', () => {
  const result = validateQueue(queue([validCommand({ action: 'click_anything' })]), NOW);
  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /action/i);
});

test('rejects duplicate command ids', () => {
  const c = validCommand();
  const result = validateQueue(queue([c, { ...c }]), NOW);
  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /duplicate/i);
});

test('rejects retry ceilings greater than one', () => {
  const result = validateQueue(queue([validCommand({ retry: { max_attempts: 2 } })]), NOW);
  assert.equal(result.ok, false);
  assert.match(result.errors.join('\n'), /max_attempts/i);
});

test('allows only canonical Google Flow origins', () => {
  assert.equal(isAllowedFlowUrl('https://flow.google.com/project/123'), true);
  assert.equal(isAllowedFlowUrl('https://labs.google/fx/tools/flow/project/123'), true);
  assert.equal(isAllowedFlowUrl('https://evil.example.com/flow'), false);
  assert.equal(isAllowedFlowUrl('https://google.com/'), false);
});
