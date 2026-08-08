export function buildWebsiteFaviconUrl(sourceUrl?: string): string | undefined {
  const normalized = String(sourceUrl || "").trim();
  if (!normalized) return undefined;
  try {
    const url = new URL(normalized);
    if (url.protocol !== "http:" && url.protocol !== "https:") return undefined;
    return new URL("/favicon.ico", url.origin).toString();
  } catch {
    return undefined;
  }
}

export function inferWebsiteUrlFromFileName(fileName?: string): string | undefined {
  const match = String(fileName || "").trim().match(/^web_([^_]+)_/i);
  const domain = String(match?.[1] || "").trim();
  if (!domain.includes(".")) return undefined;
  return `https://${domain}`;
}
