import type { GenerationSourceSelection } from "../GenerationSourceSelector";
import type { GenerationResourceType } from "../generationRegistry";

export type GenerationDefinitionDraft<TConfig> = {
  courseId: string;
  source: GenerationSourceSelection;
  config: TConfig;
};

export type GenerationValidation = Record<string, string>;

export type GenerationConfigDefinition<TConfig extends object> = {
  resourceType: GenerationResourceType;
  title: string;
  description: string;
  defaultConfig: () => TConfig;
  validate: (config: TConfig) => GenerationValidation;
  serialize: (draft: GenerationDefinitionDraft<TConfig>) => Record<string, unknown>;
};

export type GenerationFormProps<TConfig extends object> = {
  value: TConfig;
  onChange: (value: TConfig) => void;
  errors?: GenerationValidation;
};
