// API types for the Decision Analyzer
export interface ADR {
  metadata: ADRMetadata;
  content: ADRContent;
  persona_responses?: PersonaResponse[];
}

export interface PersonaResponse {
  persona: string;
  perspective: string;
  recommended_option?: string;
  reasoning: string;
  concerns: string[];
  requirements: string[];
}

export interface ADRMetadata {
  id: string;
  title: string;
  status: ADRStatus;
  author: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  related_adrs?: string[];
  custom_fields?: Record<string, any>;
}

export interface OptionDetails {
  name: string;
  description?: string;
  pros: string[];
  cons: string[];
}

export interface ConsequencesStructured {
  positive: string[];
  negative: string[];
}

export interface ReferencedADR {
  id: string;
  title: string;
  summary: string;
}

export interface ADRContent {
  context_and_problem: string;
  decision_outcome: string;
  consequences: string;
  considered_options?: string[];
  decision_drivers?: string[];
  pros_and_cons?: string;
  options_details?: OptionDetails[];
  consequences_structured?: ConsequencesStructured;
  referenced_adrs?: ReferencedADR[];
  more_information?: string;
}

export enum ADRStatus {
  PROPOSED = "proposed",
  ACCEPTED = "accepted",
  DEPRECATED = "deprecated",
  SUPERSEDED = "superseded",
  REJECTED = "rejected"
}

export interface ADRListResponse {
  adrs: ADR[];
  total: number;
}

export interface AnalyzeADRRequest {
  adr_id: string;
  persona?: string;
}

export interface GenerateADRRequest {
  prompt: string;
  context?: string;
  tags?: string[];
  personas?: string[];
  retrieval_mode?: string;
}

export interface ModelConfig {
  name: string;
  provider?: string;
  base_url?: string;
  temperature?: number;
  num_ctx?: number;
}

export interface Persona {
  value: string;
  label: string;
  description: string;
  llm_config?: ModelConfig;
}

export interface DefaultModelConfig {
  model: string;
  provider: string;
  base_url: string;
  temperature: number;
  num_ctx: number;
}

export interface TaskResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface TaskStatus {
  status: "pending" | "progress" | "completed" | "failed";
  message?: string;
  result?: any;
  error?: string;
}

// Export/Import types
export enum ExportFormat {
  VERSIONED_JSON = "versioned_json",
  MARKDOWN = "markdown",
  JSON = "json",
  YAML = "yaml"
}

export interface ExportRequest {
  format?: string;
  adr_ids?: string[];
  exported_by?: string;
}

export interface ExportResponse {
  message: string;
  count: number;
  format: string;
  download_ready?: boolean;
}

export interface ImportRequest {
  data: any;
  overwrite_existing?: boolean;
}

export interface ImportResponse {
  message: string;
  imported_count: number;
  skipped_count?: number;
  errors?: string[];
}

export interface ExportSchemaMetadata {
  schema_version: string;
  exported_at: string;
  exported_by?: string;
  total_records: number;
}

export interface ADRExportV1 {
  id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  author?: string;
  tags: string[];
  related_adrs: string[];
  custom_fields?: Record<string, any>;
  context_and_problem: string;
  decision_drivers?: string[];
  considered_options: string[];
  decision_outcome: string;
  consequences: string;
  confirmation?: string;
  pros_and_cons?: Record<string, string[]>;
  more_information?: string;
  options_details?: Array<{
    name: string;
    description?: string;
    pros: string[];
    cons: string[];
  }>;
  consequences_structured?: {
    positive: string[];
    negative: string[];
  };
  referenced_adrs?: Array<{
    id: string;
    title: string;
    summary: string;
  }>;
  persona_responses?: any[];
}

export interface SingleADRExport {
  schema: ExportSchemaMetadata;
  adr: ADRExportV1;
}

export interface BulkADRExport {
  schema: ExportSchemaMetadata;
  adrs: ADRExportV1[];
}
