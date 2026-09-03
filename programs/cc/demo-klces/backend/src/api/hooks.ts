import { useCallback, useEffect, useState } from "react";
import { get, post } from "./client";

interface State<T> { data?: T; loading: boolean; error?: string; }
type Mutate<T> = (newData?: T) => void;

/** Simple data-fetching hook with manual re-fetch. */
export function useGet<T>(url: string | null): State<T> & { refetch: () => void } {
  const [state, setState] = useState<State<T>>({ loading: true });
  const load = useCallback(() => {
    if (!url) { setState({ loading: false }); return; }
    setState({ loading: true });
    get<T>(url)
      .then((data) => setState({ data, loading: false }))
      .catch((e) => setState({ loading: false, error: e?.message || "加载失败" }));
  }, [url]);
  useEffect(() => { load(); }, [load]);
  return { ...state, refetch: load };
}

/** Promise-based mutation helper that refetches after. */
export function usePost() {
  return async function <T>(url: string, body?: Record<string, any>): Promise<T> {
    return post<T>(url, body);
  };
}
