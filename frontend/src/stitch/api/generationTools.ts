import { apiRequest } from "./client";
import { sanitizeGenerationCatalog, type GenerationToolId } from "../shared/generation/generationCatalog";

type GenerationToolCatalogResponse = {
  tools: Array<{
    tool_id: string;
    output_scope: "personal";
    allowed_source_scopes: Array<"none" | "personal" | "course">;
    can_publish: false;
  }>;
};

export async function getGenerationTools(): Promise<GenerationToolId[]> {
  const response = await apiRequest<GenerationToolCatalogResponse>("/api/chat/v2/generation/tools");
  return sanitizeGenerationCatalog(Array.isArray(response.tools) ? response.tools : []);
}
