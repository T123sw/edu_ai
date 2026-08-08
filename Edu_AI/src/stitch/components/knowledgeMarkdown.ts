const ADMONITION_LABELS: Record<string, string> = {
  abstract: "摘要",
  note: "说明",
  info: "说明",
  tip: "提示",
  success: "要点",
  question: "思考",
  warning: "注意",
  danger: "警告",
  failure: "易错点",
  example: "示例",
  quote: "引用",
};

/**
 * Converts the small, known subset of HTML/MkDocs syntax used by imported
 * teaching materials into portable Markdown. Unknown HTML remains escaped by
 * react-markdown, so imported content never becomes executable markup.
 */
export function normalizeKnowledgeMarkdown(source: string): string {
  if (!source) return "";

  const normalized = source
    .replace(/\r\n?/g, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?(?:u|ins)>/gi, "")
    .replace(/<sub>([\s\S]*?)<\/sub>/gi, "~$1~")
    .replace(/<sup>([\s\S]*?)<\/sup>/gi, "^$1^")
    .replace(/<img\b[^>]*?src=["']([^"']+)["'][^>]*?alt=["']([^"']*)["'][^>]*>/gi, "![$2]($1)")
    .replace(/<img\b[^>]*?alt=["']([^"']*)["'][^>]*?src=["']([^"']+)["'][^>]*>/gi, "![$1]($2)")
    .replace(/<img\b[^>]*?src=["']([^"']+)["'][^>]*>/gi, "![]($1)")
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, formula: string) => `\n$$\n${formula.trim()}\n$$\n`)
    .replace(/\\\((.+?)\\\)/g, (_, formula: string) => `$${formula.trim()}$`);

  const lines = normalized.split("\n");
  const output: string[] = [];
  let inFence = false;

  for (const line of lines) {
    if (/^\s*```/.test(line)) inFence = !inFence;
    if (!inFence) {
      const match = line.match(/^\s*!!!\s+([\w-]+)(?:\s+["']?(.+?)["']?)?\s*$/i);
      if (match) {
        const fallback = ADMONITION_LABELS[match[1].toLowerCase()] ?? "说明";
        const title = match[2]?.trim() || fallback;
        output.push(`> **${title}**`);
        continue;
      }
    }
    output.push(line);
  }

  return output.join("\n").replace(/\n{4,}/g, "\n\n\n").trim();
}
