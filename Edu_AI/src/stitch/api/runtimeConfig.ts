import { apiRequest } from "./client";

export type RuntimeConfigScope = "user" | "system";
export type RuntimeProvider =
  | "llm"
  | "embedding"
  | "tts"
  | "web_search"
  | "pdf_parser"
  | "classroom";
export type RuntimeRevisionStatus =
  | "draft"
  | "verified"
  | "invalid"
  | "active"
  | "superseded";

export type RuntimeConfigRevision = {
  revision_id: string;
  status: RuntimeRevisionStatus;
  created_at: string;
  verified_at?: string | null;
  activated_at?: string | null;
  validation_error?: string | null;
  values: Record<string, string | number>;
};

export type RuntimeProviderRecord = {
  scope: RuntimeConfigScope;
  owner_id: string;
  provider: RuntimeProvider;
  active_revision_id?: string | null;
  revisions: RuntimeConfigRevision[];
};

export type RuntimeProviderStatus = {
  provider: RuntimeProvider;
  fields: string[];
  effective_source: RuntimeConfigScope | "environment";
  effective_revision_id?: string | null;
  user: RuntimeProviderRecord;
  system?: RuntimeProviderRecord | null;
};

export type RuntimeConfigOverview = {
  providers: RuntimeProviderStatus[];
  can_manage_system: boolean;
};

export function getRuntimeConfigOverview() {
  return apiRequest<RuntimeConfigOverview>("/api/runtime-config");
}

export function saveRuntimeConfigDraft(
  provider: RuntimeProvider,
  scope: RuntimeConfigScope,
  values: Record<string, string | number>,
) {
  return apiRequest<RuntimeConfigRevision>(`/api/runtime-config/${provider}/draft`, {
    method: "POST",
    body: JSON.stringify({ scope, values }),
  });
}

export function verifyRuntimeConfig(
  provider: RuntimeProvider,
  scope: RuntimeConfigScope,
  revisionId: string,
) {
  return apiRequest<RuntimeConfigRevision>(`/api/runtime-config/${provider}/verify`, {
    method: "POST",
    body: JSON.stringify({ scope, revision_id: revisionId }),
  });
}

export function activateRuntimeConfig(
  provider: RuntimeProvider,
  scope: RuntimeConfigScope,
  revisionId: string,
) {
  return apiRequest<RuntimeConfigRevision>(`/api/runtime-config/${provider}/activate`, {
    method: "POST",
    body: JSON.stringify({ scope, revision_id: revisionId }),
  });
}

export function rollbackRuntimeConfig(provider: RuntimeProvider, scope: RuntimeConfigScope) {
  return apiRequest<RuntimeConfigRevision>(`/api/runtime-config/${provider}/rollback`, {
    method: "POST",
    body: JSON.stringify({ scope }),
  });
}
