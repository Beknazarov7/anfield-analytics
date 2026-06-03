import { useEffect, useState } from "react";

/**
 * Tiny fetch hook for our static JSON files. Returns { data, loading, error }.
 * The pipeline output never changes at runtime, so a one-shot fetch is all we
 * need — no caching library required.
 */
export function useJson(url) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((error) => !cancelled && setState({ data: null, loading: false, error }));
    return () => {
      cancelled = true;
    };
  }, [url]);

  return state;
}
