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
  proposed_principle?: string;
  reasoning?: string;
  rationale?: string;
  concerns: string[];
  requirements: string[];
  implications?: string[];
  counter_arguments?: string[];
  proof_statements?: string[];
  exceptions?: string[];
  refinement_history?: string[];
}

export interface ADRMetadata {
  id: string;
  title: string;
  status: ADRStatus;
  record_type?: 'decision' | 'principle';
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

export interface PrincipleDetails {
  statement: string;
  rationale: string;
  implications: string[];
  counter_arguments: string[];
  proof_statements: string[];
  exceptions: string[];
}

export interface ReferencedADR {
  id: string;
  title: string;
  summary: string;
  type?: 'decision' | 'principle' | 'mcp';
  server_name?: string;  // For MCP references, e.g., "Websearch"
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
  principle_details?: PrincipleDetails;
  referenced_adrs?: ReferencedADR[];
  more_information?: string;
  original_generation_prompt?: OriginalGenerationPrompt;
}

export interface OriginalGenerationPrompt {
  title: string;
  context: string;
  problem_statement: string;
  constraints?: string[];
  stakeholders?: string[];
  tags?: string[];
  retrieval_mode: string;
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
  provider_id?: string;
  record_type?: 'decision' | 'principle';
  use_mcp?: boolean;
  status_filter?: string[];
}

export interface PersonaRefinementItem {
  persona: string;
  refinement_prompt: string;
}

export interface RefinePersonasRequest {
  refinements: PersonaRefinementItem[];
  refinements_to_delete?: Record<string, number[]>;
  provider_id?: string;
}

export interface RefineOriginalPromptRequest {
  title?: string;
  context?: string;
  problem_statement?: string;
  constraints?: string[];
  stakeholders?: string[];
  retrieval_mode?: string;
  provider_id?: string;
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
  status: "pending" | "progress" | "completed" | "failed" | "revoked";
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

export interface ImportResponse {
  message: string;
  imported_count: number;
  skipped_count: number;
  errors: string[];
  imported_ids?: string[];
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

/** @public */
export interface SingleADRExport {
  schema: ExportSchemaMetadata;
  adr: ADRExportV1;
}

/** @public */
export interface BulkADRExport {
  schema: ExportSchemaMetadata;
  adrs: ADRExportV1[];
}

// LLM Provider Configuration types
export interface LLMProvider {
  id: string;
  name: string;
  provider_type: string;  // ollama, openai, openrouter, vllm, llama_cpp, custom
  base_url: string;
  model_name: string;
  has_api_key: boolean;
  temperature: number;
  num_ctx?: number;
  num_predict?: number;
  parallel_requests_enabled: boolean;
  max_parallel_requests: number;
  is_default: boolean;
  is_env_based: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProviderRequest {
  name: string;
  provider_type: string;
  base_url: string;
  model_name: string;
  api_key?: string;
  temperature?: number;
  num_ctx?: number;
  num_predict?: number;
  parallel_requests_enabled?: boolean;
  max_parallel_requests?: number;
  is_default?: boolean;
}

export interface UpdateProviderRequest {
  name?: string;
  provider_type?: string;
  base_url?: string;
  model_name?: string;
  api_key?: string;
  temperature?: number;
  num_ctx?: number;
  num_predict?: number;
  parallel_requests_enabled?: boolean;
  max_parallel_requests?: number;
  is_default?: boolean;
}

export interface ProvidersListResponse {
  providers: LLMProvider[];
}

// Persona Management types
export interface ModelConfigInfo {
  name: string;
  provider?: string;
  base_url?: string;
  temperature?: number;
  num_ctx?: number;
}

export interface PersonaConfig {
  name: string;
  description: string;
  instructions: string;
  focus_areas: string[];
  evaluation_criteria: string[];
  model_config?: ModelConfigInfo;
}

export interface PersonaInfo {
  value: string;
  label: string;
  description: string;
  llm_config?: ModelConfigInfo;
}

export interface PersonaCreateRequest {
  name: string;
  description: string;
  instructions: string;
  focus_areas: string[];
  evaluation_criteria: string[];
  llm_config?: ModelConfigInfo;
}

export interface PersonaUpdateRequest {
  name?: string;
  description?: string;
  instructions?: string;
  focus_areas?: string[];
  evaluation_criteria?: string[];
  llm_config?: ModelConfigInfo;
}

export interface PersonaGenerateRequest {
  prompt: string;
  provider_id?: string;
}

export interface PersonaRefineRequest {
  prompt: string;
  current_persona: PersonaConfig;
  provider_id?: string;
}

// MCP (Model Context Protocol) types
export enum MCPTransportType {
  STDIO = "stdio",
  HTTP = "http",
  SSE = "sse"
}

export enum MCPToolExecutionMode {
  INITIAL_ONLY = "initial_only",
  PER_PERSONA = "per_persona"
}

export interface MCPToolConfig {
  tool_name: string;
  display_name: string;
  description: string;
  default_enabled: boolean;
  execution_mode: MCPToolExecutionMode;
  default_arguments: Record<string, any>;
  context_argument_mappings?: Record<string, string>;
}

export interface MCPServerConfig {
  id: string;
  name: string;
  description?: string;
  transport_type: MCPTransportType;
  command?: string;
  args?: string[];
  url?: string;
  headers?: Record<string, string>;
  auth_type?: string;
  has_auth_token: boolean;
  tools: MCPToolConfig[];
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateMCPServerRequest {
  name: string;
  description?: string;
  transport_type: MCPTransportType;
  command?: string;
  args?: string[];
  url?: string;
  headers?: Record<string, string>;
  auth_type?: string;
  auth_token?: string;
  is_enabled?: boolean;
}

export interface UpdateMCPServerRequest {
  name?: string;
  description?: string;
  transport_type?: MCPTransportType;
  command?: string;
  args?: string[];
  url?: string;
  headers?: Record<string, string>;
  auth_type?: string;
  auth_token?: string;
  is_enabled?: boolean;
}

export interface MCPServersListResponse {
  servers: MCPServerConfig[];
}

export interface MCPToolsListResponse {
  tools: Array<{
    server_id: string;
    server_name: string;
    tool: MCPToolConfig;
  }>;
}

export interface UpdateMCPToolRequest {
  display_name?: string;
  description?: string;
  default_enabled?: boolean;
  execution_mode?: MCPToolExecutionMode;
  default_arguments?: Record<string, any>;
  context_argument_mappings?: Record<string, string>;
}

export interface DiscoverToolsResponse {
  tools: MCPToolConfig[];
  message: string;
}

export interface MCPToolForGeneration {
  server_id: string;
  tool_name: string;
  arguments?: Record<string, any>;
  execution_mode?: MCPToolExecutionMode;
}

// Extended GenerateADRRequest with MCP tools
export interface GenerateADRRequestWithMCP extends GenerateADRRequest {
  mcp_tools?: MCPToolForGeneration[];
}

// MCP Tool Result types
export interface MCPStoredResult {
  id: string;
  server_id: string;
  server_name: string;
  tool_name: string;
  arguments: Record<string, any>;
  result: any;
  success: boolean;
  error?: string;
  created_at: string;
  adr_id?: string;
}

export interface MCPResultSummary {
  id: string;
  server_name: string;
  tool_name: string;
  success: boolean;
  created_at: string;
  adr_id?: string;
}

export interface MCPResultsListResponse {
  results: MCPResultSummary[];
}
