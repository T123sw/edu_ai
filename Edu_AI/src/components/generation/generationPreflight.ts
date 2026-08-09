import type { GenerationResourceType } from "./generationRegistry";

export function generationPreflightResourceType(resourceType: GenerationResourceType) {
  return resourceType === "mind_map" ? "graph" : resourceType;
}
