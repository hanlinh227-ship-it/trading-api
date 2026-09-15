import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretTaskIntent } from '../src/task-intent.js'

test('Vietnamese negation remains a constraint rather than requested mutation', () => {
  const intent = interpretTaskIntent('Chơi 2048 đến khi thua, không mua gì, không bấm quảng cáo')
  assert.equal(intent.riskClass, 'A')
  assert.equal(intent.persistence, 'UNTIL_TERMINAL')
  assert.ok(intent.forbiddenActions.includes('PURCHASE'))
  assert.ok(intent.forbiddenActions.includes('OPEN_AD'))
})

test('Vietnamese destructive intent remains class C', () => {
  assert.equal(interpretTaskIntent('Xóa 10 tin nhắn này').riskClass, 'C')
  assert.equal(interpretTaskIntent('Gửi tin nhắn này ngay').riskClass, 'C')
})
