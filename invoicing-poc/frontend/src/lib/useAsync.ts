import { useCallback, useEffect, useState } from "react";

// Tiny data-loading hook: { data, error, loading, reload }.
// Keeps each component free of repeated useEffect/loading/error boilerplate.
export function useAsync<T>(loader: () => Promise<T>) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null, error: null, loading: true,
  });

  const reload = useCallback(async () => {
    try {
      const data = await loader();
      setState({ data, error: null, loading: false });
    } catch (err) {
      setState((s) => ({ ...s, error: err instanceof Error ? err.message : "Failed to load", loading: false }));
    }
  }, [loader]);

  useEffect(() => {
    // Async IIFE: state is set after the await, never synchronously in the effect body.
    void (async () => {
      try {
        const data = await loader();
        setState({ data, error: null, loading: false });
      } catch (err) {
        setState((s) => ({ ...s, error: err instanceof Error ? err.message : "Failed to load", loading: false }));
      }
    })();
  }, [loader]);

  return { ...state, reload };
}
