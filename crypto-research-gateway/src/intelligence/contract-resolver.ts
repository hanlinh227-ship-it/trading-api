export type ContractEntitlement = 'VERIFIED_REALTIME' | 'VERIFIED_DELAYED' | 'UNVERIFIED';

export type ContractCandidate = {
  productCode: string;
  ticker: string;
  expiry: string;
  active: boolean;
  entitlement: ContractEntitlement;
};

export type ContractResolution =
  | { status: 'RESOLVED'; contract: ContractCandidate }
  | { status: 'BLOCKED'; reason: 'CONTRACT_UNRESOLVED' | 'CONTRACT_EXPIRED' };

function parsedExpiry(candidate: ContractCandidate): number | null {
  const value = Date.parse(candidate.expiry);
  return Number.isFinite(value) ? value : null;
}

export function resolveCurrentContract(
  productCode: string,
  candidates: readonly ContractCandidate[],
  nowMs: number,
): ContractResolution {
  const canonicalProduct = productCode.trim().toUpperCase();
  if (!canonicalProduct || !Number.isFinite(nowMs)) {
    return { status: 'BLOCKED', reason: 'CONTRACT_UNRESOLVED' };
  }

  const sameProduct = candidates.filter(
    (candidate) => candidate.productCode.trim().toUpperCase() === canonicalProduct,
  );
  if (sameProduct.length === 0) {
    return { status: 'BLOCKED', reason: 'CONTRACT_UNRESOLVED' };
  }

  const eligible = sameProduct
    .map((candidate) => ({ candidate, expiryMs: parsedExpiry(candidate) }))
    .filter(
      (item): item is { candidate: ContractCandidate; expiryMs: number } =>
        item.expiryMs !== null
        && item.expiryMs > nowMs
        && item.candidate.active === true
        && item.candidate.entitlement === 'VERIFIED_REALTIME',
    )
    .sort((left, right) => {
      if (left.expiryMs !== right.expiryMs) return left.expiryMs - right.expiryMs;
      return left.candidate.ticker.localeCompare(right.candidate.ticker);
    });

  if (eligible.length > 0) {
    return { status: 'RESOLVED', contract: eligible[0].candidate };
  }

  const parseable = sameProduct
    .map((candidate) => parsedExpiry(candidate))
    .filter((value): value is number => value !== null);
  if (parseable.length > 0 && parseable.every((expiryMs) => expiryMs <= nowMs)) {
    return { status: 'BLOCKED', reason: 'CONTRACT_EXPIRED' };
  }

  return { status: 'BLOCKED', reason: 'CONTRACT_UNRESOLVED' };
}
