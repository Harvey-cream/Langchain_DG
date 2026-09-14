import { useEffect, useState } from 'react';
import { getAnalysis, errorText } from '../api/demo';
import type { Analysis } from '../api/demo';

export function useContractAnalysis(contractId: string, versionId: string, refreshKey: number) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setAnalysis(null);
    setError('');
    setLoading(Boolean(versionId));
    if (!versionId) return;

    async function poll() {
      try {
        const response = await getAnalysis(contractId, versionId);
        if (disposed) return;
        const next = response.data ?? null;
        setAnalysis(next);
        setLoading(false);
        if (next && ['pending', 'parsing', 'analyzing'].includes(next.status)) {
          timer = setTimeout(poll, 2000);
        }
      } catch (cause) {
        if (disposed) return;
        setError(errorText(cause));
        setLoading(false);
      }
    }

    void poll();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [contractId, versionId, refreshKey]);

  return { analysis, loading, error };
}
