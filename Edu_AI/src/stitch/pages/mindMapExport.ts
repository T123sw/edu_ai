export function serializeMindMapContent(content: unknown): string {
  const payload = content && typeof content === "object" && !Array.isArray(content)
    ? content as Record<string, unknown>
    : {};
  const root = payload.root;
  if (!root || typeof root !== "object" || Array.isArray(root)) {
    throw new Error("思维导图缺少根节点，无法导出");
  }
  return JSON.stringify(payload, null, 2);
}

export function downloadMindMapJson(content: unknown, title: string): void {
  const body = serializeMindMapContent(content);
  const blob = new Blob([body], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${title.trim().replace(/[\\/:*?"<>|]+/g, "-") || "思维导图"}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}
