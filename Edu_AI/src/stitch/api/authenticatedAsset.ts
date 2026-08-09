export function requiresAuthenticatedAssetFetch(url: string): boolean {
  return url.startsWith("/api/");
}
