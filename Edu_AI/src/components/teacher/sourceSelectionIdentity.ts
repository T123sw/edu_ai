export type SourceSelectableFile = {
  key: string;
  documentId?: string;
};

/**
 * Knowledge-base APIs expose a stable public document id, while `key` is the
 * preview location (a URL or storage path). Retrieval and generation must use
 * the public id whenever it exists.
 */
export function sourceSelectionId(file: SourceSelectableFile): string {
  return String(file.documentId || file.key).trim();
}
