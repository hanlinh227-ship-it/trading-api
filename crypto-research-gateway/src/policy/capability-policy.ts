export type CapabilityMode = 'RESEARCH_SAFE' | 'AUTH_READ_ONLY' | 'HIGH_RISK';

export type CapabilityDecision = {
  allowed: boolean;
  reason: string;
};

export function authorizeCapability(_id: string, mode: CapabilityMode): CapabilityDecision {
  if (mode === 'RESEARCH_SAFE') {
    return { allowed: true, reason: 'research_safe' };
  }
  if (mode === 'AUTH_READ_ONLY') {
    return { allowed: false, reason: 'auth_read_only_disabled' };
  }
  if (mode === 'HIGH_RISK') {
    return { allowed: false, reason: 'high_risk_disabled' };
  }
  return { allowed: false, reason: 'unknown_mode' };
}
