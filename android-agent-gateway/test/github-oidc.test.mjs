import test from 'node:test'
import assert from 'node:assert/strict'
import { validateGitHubClaims } from '../src/github-oidc.js'

const valid = {
  iss: 'https://token.actions.githubusercontent.com',
  aud: 'android-brain-agent-gateway',
  repository: 'hanlinh227-ship-it/trading-api',
  repository_id: '1335593524',
  repository_owner: 'hanlinh227-ship-it',
  actor: 'hanlinh227-ship-it',
  event_name: 'issues',
  exp: Math.floor(Date.now() / 1000) + 300,
  nbf: Math.floor(Date.now() / 1000) - 10,
}

test('github oidc claims accept only exact trusted repo owner and issues event', () => {
  assert.equal(validateGitHubClaims(valid), true)
  assert.throws(() => validateGitHubClaims({...valid, repository: 'attacker/repo'}))
  assert.throws(() => validateGitHubClaims({...valid, actor: 'attacker'}))
  assert.throws(() => validateGitHubClaims({...valid, event_name: 'pull_request'}))
})
