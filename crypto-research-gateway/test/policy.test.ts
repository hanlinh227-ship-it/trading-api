import { describe, expect, it } from 'vitest';
import { authorizeCapability } from '../src/policy/capability-policy.js';

describe('authorizeCapability', () => {
  it('allows research-safe capability', () => {
    expect(authorizeCapability('market_snapshot', 'RESEARCH_SAFE')).toEqual({ allowed: true, reason: 'research_safe' });
  });

  it('denies authenticated read-only by default', () => {
    expect(authorizeCapability('private_positions', 'AUTH_READ_ONLY').allowed).toBe(false);
  });

  it('denies high-risk capability unconditionally', () => {
    expect(authorizeCapability('place_order', 'HIGH_RISK').allowed).toBe(false);
  });

  it('fails closed for unknown mode', () => {
    expect(authorizeCapability('unknown', 'UNKNOWN' as never).allowed).toBe(false);
  });
});
