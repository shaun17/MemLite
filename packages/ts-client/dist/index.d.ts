type SearchMode = "auto" | "episodic" | "semantic" | "mixed";
interface ProjectResponse {
    org_id: string;
    project_id: string;
    description: string | null;
    created_at: string;
    updated_at: string;
}
interface EpisodeInput {
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
interface EpisodeResponse {
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
interface CombinedMemoryItemResponse {
    source: "episodic" | "semantic";
    content: string;
    identifier: string;
    score: number;
}
interface EpisodicMatchResponse {
    episode: EpisodeResponse;
    derivative_uid: string;
    score: number;
}
interface SemanticFeatureResponse {
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
interface MemorySearchResponse {
    mode: string;
    rewritten_query: string;
    subqueries: string[];
    episodic_matches: EpisodicMatchResponse[];
    semantic_features: SemanticFeatureResponse[];
    combined: CombinedMemoryItemResponse[];
    expanded_context: EpisodeResponse[];
    short_term_context: string;
}
interface AgentModeResponse {
    search: MemorySearchResponse;
    context_text: string;
}
interface MemLiteClientOptions {
    baseUrl: string;
    retries?: number;
    retryBackoffMs?: number;
    fetchImpl?: typeof fetch;
    headers?: Record<string, string>;
}
interface ProjectCreateInput {
    orgId: string;
    projectId: string;
    description?: string | null;
}
interface ProjectListInput {
    orgId?: string;
}
interface MemoryAddInput {
    sessionKey: string;
    semanticSetId?: string | null;
    episodes: EpisodeInput[];
}
interface MemorySearchInput {
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

declare class MemLiteMemoryApi {
    private readonly client;
    constructor(client: MemLiteClient);
    add(input: MemoryAddInput): Promise<string[]>;
    search(input: MemorySearchInput): Promise<MemorySearchResponse>;
    agent(input: MemorySearchInput): Promise<AgentModeResponse>;
    list(input: {
        sessionKey: string;
    }): Promise<EpisodeResponse[]>;
    deleteEpisodes(input: {
        episodeUids: string[];
        semanticSetId?: string | null;
    }): Promise<void>;
}

declare class MemLiteProjectApi {
    private readonly client;
    constructor(client: MemLiteClient);
    create(input: ProjectCreateInput): Promise<void>;
    get(input: {
        orgId: string;
        projectId: string;
    }): Promise<ProjectResponse>;
    list(input?: ProjectListInput): Promise<ProjectResponse[]>;
    delete(input: {
        orgId: string;
        projectId: string;
    }): Promise<void>;
    episodeCount(input: {
        orgId: string;
        projectId: string;
    }): Promise<number>;
}

declare class MemLiteClient {
    readonly baseUrl: string;
    readonly projects: MemLiteProjectApi;
    readonly memory: MemLiteMemoryApi;
    private readonly retries;
    private readonly retryBackoffMs;
    private readonly fetchImpl;
    private readonly headers;
    constructor(options: MemLiteClientOptions);
    request<T>(method: string, path: string, options?: {
        query?: Record<string, string | number | null | undefined>;
        body?: unknown;
    }): Promise<T>;
}

declare class MemLiteClientError extends Error {
    constructor(message: string);
}
declare class MemLiteApiError extends MemLiteClientError {
    statusCode: number;
    responseBody: unknown;
    constructor(message: string, statusCode: number, responseBody: unknown);
}

export { type AgentModeResponse, type EpisodeInput, type EpisodeResponse, MemLiteApiError, MemLiteClient, MemLiteClientError, type MemorySearchResponse, type ProjectResponse, type SearchMode };
