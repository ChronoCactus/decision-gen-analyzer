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
  created_date: string;
  tags: string[];
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
}

export interface Persona {
  value: string;
  label: string;
  description: string;
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
