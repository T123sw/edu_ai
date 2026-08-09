import { useEffect, useState } from "react";

import { apiBlob } from "./client";
import { requiresAuthenticatedAssetFetch } from "./authenticatedAsset";

type AuthenticatedBlobUrlState = {
  url: string;
  loading: boolean;
  error: string | null;
};

export function useAuthenticatedBlobUrl(sourceUrl: string): AuthenticatedBlobUrlState {
  const [state, setState] = useState<AuthenticatedBlobUrlState>({
    url: requiresAuthenticatedAssetFetch(sourceUrl) ? "" : sourceUrl,
    loading: Boolean(sourceUrl && requiresAuthenticatedAssetFetch(sourceUrl)),
    error: null,
  });

  useEffect(() => {
    if (!sourceUrl) {
      setState({ url: "", loading: false, error: null });
      return;
    }
    if (!requiresAuthenticatedAssetFetch(sourceUrl)) {
      setState({ url: sourceUrl, loading: false, error: null });
      return;
    }

    let disposed = false;
    let objectUrl = "";
    setState({ url: "", loading: true, error: null });
    void apiBlob(sourceUrl)
      .then((blob) => {
        if (disposed) return;
        objectUrl = URL.createObjectURL(blob);
        setState({ url: objectUrl, loading: false, error: null });
      })
      .catch((reason) => {
        if (disposed) return;
        setState({
          url: "",
          loading: false,
          error: reason instanceof Error ? reason.message : "资源加载失败",
        });
      });

    return () => {
      disposed = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [sourceUrl]);

  return state;
}
