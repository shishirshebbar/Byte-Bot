import { createContext, useContext, useEffect, useId, useLayoutEffect } from 'react';
import type { ClaimResult, Investigation } from './investigation-types';

type PresentationActions = {
  showCase: (data: Investigation | undefined) => void;
  showStatus: (id: string, status: Pick<Investigation, 'case_status' | 'status_revision'>) => void;
  showClaim: (result: ClaimResult | undefined) => void;
  lock: (id: string, locked: boolean) => void;
};

export const PresentationState = createContext<PresentationActions | null>(null);

export function useCaseSnapshot(data: Investigation | undefined) {
  const showCase = useContext(PresentationState)?.showCase;
  useEffect(() => { if (data) showCase?.(data); }, [showCase, data]);
}

/** Mirrors a payment-claim check onto the presenter stage (Case 1). Nothing is stored. */
export function useClaimSnapshot(result: ClaimResult | undefined) {
  const showClaim = useContext(PresentationState)?.showClaim;
  useEffect(() => { showClaim?.(result); }, [showClaim, result]);
  useEffect(() => () => showClaim?.(undefined), [showClaim]);
}

export function usePhoneLock(locked: boolean) {
  const lock = useContext(PresentationState)?.lock;
  const id = useId();
  useLayoutEffect(() => {
    if (!locked || !lock) return;
    lock(id, true);
    return () => lock(id, false);
  }, [id, lock, locked]);
}
