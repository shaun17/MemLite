export type SearchMode = "auto" | "episodic" | "semantic" | "mixed";

export interface ProjectResponse {
  org_id: string;
  project_id: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface EpisodeInput {
  uid: string;
  session_key: string;
  session_id: string;
  producer_id: string;
  producer_role: string;
  produced_for_id?: string | null;
  sequence_num?: number;
  content: string;
  content_type?: string;
  episode_type?: string;
  metadata_json?: string | null;
  filterable_metadata_json?: string | null;
}

export interface EpisodeResponse {
  uid: string;
  session_key: string;
  session_id: string;
  producer_id: string;
  producer_role: string;
  produced_for_id: string | null;
  sequence_num: number;
  content: string;
  content_type: string;
  episode_type: string;
  created_at: string;
  metadata_json: string | null;
  filterable_metadata_json: string | null;
  deleted: number;
}

export interface CombinedMemoryItemResponse {
  source: "episodic" | "semantic";
  content: string;
  identifier: string;
  score: number;
}

export interface EpisodicMatchResponse {
  episode: EpisodeResponse;
  derivative_uid: string;
  score: number;
}

export interface SemanticFeatureResponse {
  id: number;
  set_id: string;
  category: string;
  tag: string;
  feature_name: string;
  value: string;
  metadata_json: string | null;
  created_at: string;
  updated_at: string;
  deleted: number;
}

export interface MemorySearchResponse {
  mode: string;
  rewritten_query: string;
  subqueries: string[];
  episodic_matches: EpisodicMatchResponse[];
  semantic_features: SemanticFeatureResponse[];
  combined: CombinedMemoryItemResponse[];
  expanded_context: EpisodeResponse[];
  short_term_context: string;
}

export interface AgentModeResponse {
  search: MemorySearchResponse;
  context_text: string;
}

export interface MemLiteClientOptions {
  baseUrl: string;
  retries?: number;
  retryBackoffMs?: number;
  fetchImpl?: typeof fetch;
  headers?: Record<string, string>;
}

export interface ProjectCreateInput {
  orgId: string;
  projectId: string;
  description?: string | null;
}

export interface ProjectListInput {
  orgId?: string;
}

export interface MemoryAddInput {
  sessionKey: string;
  semanticSetId?: string | null;
  episodes: EpisodeInput[];
}

export interface MemorySearchInput {
  query: string;
  sessionKey?: string;
  sessionId?: string;
  semanticSetId?: string | null;
  mode?: SearchMode;
  limit?: number;
  contextWindow?: number;
  minScore?: number;
  producerRole?: string;
  episodeType?: string;
}
