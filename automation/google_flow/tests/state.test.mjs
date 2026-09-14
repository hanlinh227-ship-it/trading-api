import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldProcess, markState, nextRunnableCommand, clearInflight } from '../chrome_extension/lib/state.js';

const NOW = Date.parse('2026-09-14T06:00:00Z');
const cmd = (id, overrides={}) => ({
  command_id:id,
  created_at:'2026-09-14T05:00:00Z',
  not_before:null,
  expires_at:'2026-09-15T05:00:00Z',
  scene:24,
  ...overrides
});

test('does not reprocess completed command after restart', () => {
  const history = { items: { a: { state:'completed', attempts:1, updated_at:'2026-09-14T05:10:00Z' } }, order:['a'] };
  assert.deepEqual(shouldProcess(cmd('a'), history, NOW), { process:false, reason:'already-final' });
});

test('respects not_before', () => {
  const result = shouldProcess(cmd('a',{not_before:'2026-09-14T07:00:00Z'}), {items:{},order:[]}, NOW);
  assert.equal(result.process, false);
  assert.equal(result.reason, 'not-before');
});

test('skips expired commands', () => {
  const result = shouldProcess(cmd('a',{expires_at:'2026-09-14T05:30:00Z'}), {items:{},order:[]}, NOW);
  assert.equal(result.process, false);
  assert.equal(result.reason, 'expired');
});

test('returns oldest runnable command chronologically', () => {
  const commands = [
    cmd('b',{created_at:'2026-09-14T05:20:00Z'}),
    cmd('a',{created_at:'2026-09-14T05:10:00Z'})
  ];
  assert.equal(nextRunnableCommand(commands,{items:{},order:[]},NOW).command_id,'a');
});

test('markState stores sanitized data and trims history', () => {
  let history = {items:{},order:[]};
  history = markState(history,'a','submitted',{scene:1,attempts:1,error_code:null,secret:'must-not-persist'},3,NOW);
  history = markState(history,'b','completed',{scene:2,attempts:1},3,NOW+1);
  history = markState(history,'c','completed',{scene:3,attempts:1},3,NOW+2);
  history = markState(history,'d','completed',{scene:4,attempts:1},3,NOW+3);
  assert.deepEqual(history.order,['b','c','d']);
  assert.equal(history.items.a, undefined);
  assert.equal('secret' in history.items.d,false);
  assert.equal(history.items.d.scene,4);
});

test('does not reprocess an in-flight submitted command after polling or restart', () => {
  const history = { items: { a: { state:'submitted', attempts:1, updated_at:'2026-09-14T05:10:00Z' } }, order:['a'] };
  assert.deepEqual(shouldProcess(cmd('a'), history, NOW), { process:false, reason:'already-inflight' });
});

test('does not start another queue command while any command is in flight', () => {
  const history = { items: { a: { state:'waiting', attempts:1, updated_at:'2026-09-14T05:10:00Z' } }, order:['a'] };
  const commands = [cmd('b',{created_at:'2026-09-14T05:20:00Z'})];
  assert.equal(nextRunnableCommand(commands, history, NOW), null);
});

test('manual recovery converts in-flight locks into final blocked states', () => {
  const history = {
    items: {
      a:{state:'submitted',attempts:1,scene:24,updated_at:'2026-09-14T05:00:00Z'},
      b:{state:'completed',attempts:1,scene:23,updated_at:'2026-09-14T04:00:00Z'}
    },
    order:['b','a']
  };
  const next = clearInflight(history, NOW);
  assert.equal(next.items.a.state,'blocked');
  assert.equal(next.items.a.error_code,'MANUAL_RESET');
  assert.equal(next.items.b.state,'completed');
});
