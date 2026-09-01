import { apiRequest } from "./client";
import type { KnowledgeBaseDocument, KnowledgeBaseDocumentContent } from "./types";
import type { JobRecord } from "../../jobs/types";

export type PersonalKnowledgeDocument = Omit<KnowledgeBaseDocument, "course_id" | "library_type"> & {
  course_context_id?: string | null;
  library_type?: "personal";
};

export function listPersonalKnowledgeDocuments(options?: { search?: string; status?: string; limit?: number; offset?: number }) {
  const params = new URLSearchParams();
  if (options?.search) params.set("search", options.search);
  if (options?.status) params.set("document_status", options.status);
  if (typeof options?.limit === "number") params.set("limit", String(options.limit));
  if (typeof options?.offset === "number") params.set("offset", String(options.offset));
  const query = params.toString();
  return apiRequest<PersonalKnowledgeDocument[]>(`/api/personal-knowledge/documents${query ? `?${query}` : ""}`);
}

export function uploadPersonalKnowledgeDocument(file: File, courseContextId?: string) {
  const body = new FormData();
  body.append("file", file);
  if (courseContextId) body.append("course_context_id", courseContextId);
  return apiRequest<{ document: PersonalKnowledgeDocument; job: JobRecord }>("/api/personal-knowledge/documents", { method: "POST", body });
}

export function getPersonalKnowledgeDocumentContent(documentId: string) {
  return apiRequest<KnowledgeBaseDocumentContent>(`/api/personal-knowledge/documents/${encodeURIComponent(documentId)}/content`);
}

export function renamePersonalKnowledgeDocument(documentId: string, displayName: string) {
  return apiRequest<PersonalKnowledgeDocument>(`/api/personal-knowledge/documents/${encodeURIComponent(documentId)}`, {
    method: "PATCH",
    body: JSON.stringify({ name: displayName }),
  });
}

export function deletePersonalKnowledgeDocument(documentId: string) {
  return apiRequest<{ message: string }>(`/api/personal-knowledge/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
}

export function retryPersonalKnowledgeDocument(documentId: string) {
  return apiRequest<JobRecord>(`/api/personal-knowledge/documents/${encodeURIComponent(documentId)}/retry`, { method: "POST" });
}
