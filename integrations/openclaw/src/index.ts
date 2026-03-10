type PluginConfig = {
  baseUrl?: string;
  userId?: string;
  orgId?: string;
  projectId?: string;
  autoCapture?: boolean;
  autoRecall?: boolean;
  searchThreshold?: number;
  topK?: number;
};

type MemoryScope = "session" | "all";

type OpenClawContext = {
  sessionKey?: string;
};

type OpenClawLogger = {
  info(message: string): void;
  warn(message: string): void;
  error(message: string): void;
};

type OpenClawPluginApi = {
  pluginConfig?: Record<string, unknown>;
  logger: OpenClawLogger;
  registerTool(factory: (ctx: OpenClawContext) => unknown, meta?: { name: string }): void;
  registerService(service: { id: string; start: () => void; stop: () => void }): void;
  on(event: string, handler: (event: any, ctx: OpenClawContext) => Promise<unknown> | unknown): void;
};

type EpisodicMatch = {
  episode: {
    uid: string;
    session_key: string;
    session_id: string;
    content: string;
    producer_role: string;
    sequence_num: number;
  };
  score: number;
};

type MemorySearchResponse = {
  episodic_matches: EpisodicMatch[];
  semantic_features?: Array<{ feature_name: string; value: string }>;
};

type HealthResponse = {
  status: string;
};

const DEFAULT_BASE_URL = "http://127.0.0.1:18731";
const DEFAULT_TOP_K = 5;
const DEFAULT_SEARCH_THRESHOLD = 0.5;
const DEFAULT_FORGET_THRESHOLD = 0.85;
const DEFAULT_PAGE_SIZE = 10;
const MAX_CAPTURE_CHARS = 4000;
const MAX_RECALL_LINE_CHARS = 500;
const MAX_RECALL_TOTAL_CHARS = 4000;
const MAX_TOOL_RESULT_MATCHES = 20;
const MAX_TOOL_RESULT_CONTENT_CHARS = 1000;

const PluginConfigJsonSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    baseUrl: { type: "string" },
    userId: { type: "string" },
    orgId: { type: "string" },
    projectId: { type: "string" },
    autoCapture: { type: "boolean" },
    autoRecall: { type: "boolean" },
    searchThreshold: { type: "number" },
    topK: { type: "number" },
  },
  required: [],
} as const;

const MemorySearchSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    query: { type: "string" },
    scope: { type: "string", enum: ["session", "all"] },
    limit: { type: "number" },
    minScore: { type: "number" },
  },
  required: ["query"],
} as const;

const MemoryStoreSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    text: { type: "string" },
    role: { type: "string", enum: ["user", "assistant", "system"] },
    metadata: { type: "object", additionalProperties: { type: "string" } },
  },
  required: ["text"],
} as const;

const MemoryGetSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    id: { type: "string" },
  },
  required: ["id"],
} as const;

const MemoryListSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    scope: { type: "string", enum: ["session", "all"] },
    pageSize: { type: "number" },
    pageNum: { type: "number" },
  },
  required: [],
} as const;

const MemoryForgetSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    memoryId: { type: "string" },
    query: { type: "string" },
    scope: { type: "string", enum: ["session", "all"] },
    minScore: { type: "number" },
  },
  required: [],
} as const;

const MemoryStatusSchema = {
  type: "object",
  additionalProperties: false,
  properties: {},
  required: [],
} as const;

class memoLiteApiClient {
  constructor(private readonly baseUrl: string) {}

  async get<T>(path: string, query?: Record<string, string | number | undefined>): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
    const response = await fetch(url, { method: "GET" });
    return parseJson<T>(response);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    return parseJson<T>(response);
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    return parseJson<T>(response);
  }

  async delete<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return parseJson<T>(response);
  }

  async health(): Promise<HealthResponse> {
    return this.get<HealthResponse>("/health");
  }
}

const parseJson = async <T>(response: Response): Promise<T> => {
  const text = await response.text();
  const payload = text ? (JSON.parse(text) as unknown) : null;
  if (!response.ok) {
    throw new Error(`${response.status}: ${JSON.stringify(payload)}`);
  }
  return payload as T;
};

function resolvePluginConfig(api: OpenClawPluginApi): PluginConfig {
  const raw = api.pluginConfig ?? {};
  return {
    baseUrl: typeof raw.baseUrl === "string" ? raw.baseUrl.trim() : undefined,
    userId: typeof raw.userId === "string" ? raw.userId.trim() : undefined,
    orgId: typeof raw.orgId === "string" ? raw.orgId.trim() : undefined,
    projectId: typeof raw.projectId === "string" ? raw.projectId.trim() : undefined,
    autoCapture: typeof raw.autoCapture === "boolean" ? raw.autoCapture : undefined,
    autoRecall: typeof raw.autoRecall === "boolean" ? raw.autoRecall : undefined,
    searchThreshold:
      typeof raw.searchThreshold === "number" ? raw.searchThreshold : undefined,
    topK: typeof raw.topK === "number" ? raw.topK : undefined,
  };
}

function requireProjectConfig(
  cfg: PluginConfig,
): Required<Pick<PluginConfig, "orgId" | "projectId">> {
  if (!cfg.orgId || !cfg.projectId) {
    throw new Error("Missing orgId/projectId in plugin config.");
  }
  return { orgId: cfg.orgId, projectId: cfg.projectId };
}

function normalizeScope(value: unknown, fallback: MemoryScope): MemoryScope {
  return value === "session" || value === "all" ? value : fallback;
}

function resolveQueryScope(
  rawQuery: string,
  explicitScope: MemoryScope | undefined,
  fallback: MemoryScope,
): { scope: MemoryScope; query: string } {
  const query = rawQuery.trim();
  const allPrefix = /^(?:@all|all|scope\s*[:=]\s*all)\s*[:：]?\s*/i;
  const sessionPrefix = /^(?:@session|session|scope\s*[:=]\s*session)\s*[:：]?\s*/i;

  if (allPrefix.test(query)) {
    return { scope: "all", query: query.replace(allPrefix, "").trim() };
  }
  if (sessionPrefix.test(query)) {
    return { scope: "session", query: query.replace(sessionPrefix, "").trim() };
  }
  if (explicitScope) {
    return { scope: explicitScope, query };
  }

  const globalPattern =
    /(查询全部|全部信息|所有信息|所有记忆|全部记忆|全局|跨会话|scope\s*=\s*all|all\s+memories|all\s+sessions)/i;
  if (globalPattern.test(query)) {
    return { scope: "all", query };
  }
  return { scope: fallback, query };
}

function readStringParam(
  params: Record<string, unknown>,
  name: string,
  options: { required?: boolean } = {},
): string | undefined {
  const value = params[name];
  if (typeof value === "string" && value.length > 0) {
    return value;
  }
  if (options.required) {
    throw new Error(`Missing required string param: ${name}`);
  }
  return undefined;
}

function readNumberParam(params: Record<string, unknown>, name: string): number | undefined {
  const value = params[name];
  return typeof value === "number" ? value : undefined;
}

function toMetadata(
  base: Record<string, string> | undefined,
  extras: Record<string, string | undefined>,
): Record<string, string> {
  const merged: Record<string, string> = { ...(base ?? {}) };
  for (const [key, value] of Object.entries(extras)) {
    if (value) {
      merged[key] = value;
    }
  }
  return merged;
}

async function ensureProject(client: memoLiteApiClient, cfg: PluginConfig): Promise<void> {
  const { orgId, projectId } = requireProjectConfig(cfg);
  try {
    await client.get(`/projects/${orgId}/${projectId}`);
  } catch {
    await client.post("/projects", {
      org_id: orgId,
      project_id: projectId,
    });
  }
}

async function ensureSession(
  client: memoLiteApiClient,
  cfg: PluginConfig,
  sessionKey: string,
): Promise<void> {
  const { orgId, projectId } = requireProjectConfig(cfg);
  try {
    await client.get(`/sessions/${encodeURIComponent(sessionKey)}`);
  } catch {
    await client.post("/sessions", {
      session_key: sessionKey,
      org_id: orgId,
      project_id: projectId,
      session_id: sessionKey,
      user_id: cfg.userId ?? null,
    });
  }
}

async function nextSequenceNum(client: memoLiteApiClient, sessionKey: string): Promise<number> {
  const episodes = await client.get<Array<{ sequence_num: number }>>("/memories", {
    session_key: sessionKey,
  });
  const maxSequence = episodes.reduce(
    (max, episode) => Math.max(max, episode.sequence_num),
    0,
  );
  return maxSequence + 1;
}

async function searchMemories(params: {
  client: memoLiteApiClient;
  query: string;
  scope: MemoryScope;
  sessionKey?: string;
  cfg: PluginConfig;
  limit: number;
  minScore: number;
}): Promise<MemorySearchResponse> {
  const { client, query, scope, sessionKey, cfg, limit, minScore } = params;
  return client.post<MemorySearchResponse>("/memories/search", {
    query,
    session_key: sessionKey ?? null,
    session_id: scope === "session" ? sessionKey ?? null : null,
    semantic_set_id: cfg.userId ?? sessionKey ?? null,
    mode: "episodic",
    limit,
    min_score: minScore,
  });
}

async function listMemories(params: {
  client: memoLiteApiClient;
  scope: MemoryScope;
  sessionKey?: string;
  cfg: PluginConfig;
  pageSize: number;
  pageNum: number;
}): Promise<Array<Record<string, unknown>>> {
  const { client, scope, sessionKey, cfg, pageSize, pageNum } = params;
  if (scope === "session") {
    if (!sessionKey) {
      return [];
    }
    const episodes = await client.get<Array<Record<string, unknown>>>("/memories", {
      session_key: sessionKey,
    });
    return episodes.slice(pageNum * pageSize, (pageNum + 1) * pageSize);
  }

  const sessions = await client.get<Array<{ session_key: string }>>("/sessions", {
    org_id: cfg.orgId,
    project_id: cfg.projectId,
    user_id: cfg.userId,
  });
  const allEpisodes = (
    await Promise.all(
      sessions.map((session) =>
        client.get<Array<Record<string, unknown>>>("/memories", {
          session_key: session.session_key,
        }),
      ),
    )
  ).flat();
  return allEpisodes.slice(pageNum * pageSize, (pageNum + 1) * pageSize);
}

function extractMessageTextBlocks(message: Record<string, unknown>): string[] {
  const content = message.content;
  if (typeof content === "string") {
    return [content];
  }
  if (Array.isArray(content)) {
    return content
      .map((block) => {
        if (block && typeof block === "object") {
          const record = block as Record<string, unknown>;
          if (record.type === "text" && typeof record.text === "string") {
            return record.text;
          }
        }
        return null;
      })
      .filter((text): text is string => Boolean(text));
  }
  return [];
}

function clipText(text: string, maxChars: number): string {
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, maxChars)} …[truncated ${text.length - maxChars} chars]`;
}

function formatRecallContext(result: MemorySearchResponse, limit: number): string {
  const lines: string[] = [];
  let budget = MAX_RECALL_TOTAL_CHARS;

  for (const match of result.episodic_matches.slice(0, limit)) {
    const content = clipText(match.episode.content, MAX_RECALL_LINE_CHARS);
    const line = `- [episodic] ${content} (${match.score.toFixed(2)})`;
    if (line.length > budget) {
      break;
    }
    lines.push(line);
    budget -= line.length;
  }

  for (const feature of result.semantic_features ?? []) {
    if (lines.length >= limit) {
      break;
    }
    const line = `- [semantic] ${feature.feature_name}: ${clipText(feature.value, MAX_RECALL_LINE_CHARS)}`;
    if (line.length > budget) {
      break;
    }
    lines.push(line);
    budget -= line.length;
  }

  return lines.join("\n");
}

function compactSearchResult(result: MemorySearchResponse): MemorySearchResponse {
  return {
    ...result,
    episodic_matches: (result.episodic_matches ?? []).slice(0, MAX_TOOL_RESULT_MATCHES).map((m) => ({
      ...m,
      episode: {
        ...m.episode,
        content: clipText(m.episode.content, MAX_TOOL_RESULT_CONTENT_CHARS),
      },
    })),
    semantic_features: (result.semantic_features ?? []).slice(0, MAX_TOOL_RESULT_MATCHES).map((f) => ({
      ...f,
      value: clipText(f.value, MAX_TOOL_RESULT_CONTENT_CHARS),
    })),
  };
}

async function autoCaptureMessages(params: {
  api: OpenClawPluginApi;
  client: memoLiteApiClient;
  cfg: PluginConfig;
  sessionKey?: string;
  messages: unknown[];
}): Promise<void> {
  const { api, client, cfg, sessionKey, messages } = params;
  if (!sessionKey) {
    return;
  }
  await ensureProject(client, cfg);
  await ensureSession(client, cfg, sessionKey);
  let sequence = await nextSequenceNum(client, sessionKey);
  for (const message of messages.slice(-8)) {
    if (!message || typeof message !== "object") {
      continue;
    }
    const record = message as Record<string, unknown>;
    const role = typeof record.role === "string" ? record.role : "user";
    const blocks = extractMessageTextBlocks(record);
    for (const text of blocks) {
      if (text.trim().length < 5 || text.includes("relevant-memories")) {
        continue;
      }
      const normalizedText = clipText(text, MAX_CAPTURE_CHARS);
      await client.post("/memories", {
        session_key: sessionKey,
        episodes: [
          {
            uid: `${sessionKey}-${sequence}`,
            session_key: sessionKey,
            session_id: sessionKey,
            producer_id: cfg.userId ?? role,
            producer_role: role,
            sequence_num: sequence,
            content: normalizedText,
            filterable_metadata_json: JSON.stringify(
              toMetadata(undefined, {
                run_id: sessionKey,
                user_id: cfg.userId,
              }),
            ),
          },
        ],
      });
      sequence += 1;
    }
  }
  api.logger.info("openclaw-memolite: auto-capture completed");
}

async function executeSafely<T>(
  api: OpenClawPluginApi,
  operation: string,
  ctx: OpenClawContext,
  callback: () => Promise<T>,
): Promise<T | { error: string }> {
  api.logger.info(
    `openclaw-memolite: ${operation} invoked session=${ctx.sessionKey ?? "none"}`,
  );
  try {
    const result = await callback();
    api.logger.info(
      `openclaw-memolite: ${operation} succeeded session=${ctx.sessionKey ?? "none"}`,
    );
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    api.logger.warn(`openclaw-memolite: ${operation} failed: ${message}`);
    return { error: message };
  }
}

function withExecutionEnvelope<T>(
  toolName: string,
  ctx: OpenClawContext,
  data: T,
): {
  provider: "memolite";
  pluginId: "openclaw-memolite";
  tool: string;
  executed: true;
  sessionKey: string | null;
  data: T;
} {
  return {
    provider: "memolite",
    pluginId: "openclaw-memolite",
    tool: toolName,
    executed: true,
    sessionKey: ctx.sessionKey ?? null,
    data,
  };
}

function registerToolAliases(
  api: OpenClawPluginApi,
  names: string[],
  factory: (ctx: OpenClawContext, toolName: string) => unknown,
): void {
  for (const name of names) {
    api.registerTool((ctx) => factory(ctx, name), { name });
  }
}

const memlitePlugin = {
  id: "openclaw-memolite",
  name: "MemoLite",
  description: "memoLite-backed memory tools with auto recall/capture",
  kind: "memory" as const,
  configSchema: {
    jsonSchema: PluginConfigJsonSchema,
  },
  register(api: OpenClawPluginApi) {
    const cfg = resolvePluginConfig(api);
    const client = new memoLiteApiClient(cfg.baseUrl ?? DEFAULT_BASE_URL);

    registerToolAliases(api, ["memory_search", "memolite_search"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Search",
      description: "Search MemoLite memories with scope: session | all.",
      parameters: MemorySearchSchema,
      async execute(_toolCallId: string, params: Record<string, unknown>) {
        return executeSafely(api, toolName, ctx, async () => {
          const rawQuery = readStringParam(params, "query", { required: true })!;
          const explicitScope =
            params.scope === "session" || params.scope === "all"
              ? (params.scope as MemoryScope)
              : undefined;
          const { scope, query } = resolveQueryScope(rawQuery, explicitScope, "session");
          const limit = readNumberParam(params, "limit") ?? cfg.topK ?? DEFAULT_TOP_K;
          const minScore =
            readNumberParam(params, "minScore") ??
            cfg.searchThreshold ??
            DEFAULT_SEARCH_THRESHOLD;

          const result = await searchMemories({
            client,
            query,
            scope,
            sessionKey: ctx.sessionKey,
            cfg,
            limit,
            minScore,
          });
          return withExecutionEnvelope(toolName, ctx, {
            scope,
            result: compactSearchResult(result),
          });
        });
      },
    }));

    registerToolAliases(api, ["memory_store", "memolite_store"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Store",
      description: "Store an episodic MemoLite memory in the current session.",
      parameters: MemoryStoreSchema,
      async execute(_toolCallId: string, params: Record<string, unknown>) {
        return executeSafely(api, toolName, ctx, async () => {
          const text = readStringParam(params, "text", { required: true })!;
          const normalizedText = clipText(text, MAX_CAPTURE_CHARS);
          if (!ctx.sessionKey) {
            return { error: `No active session for ${toolName}` };
          }
          await ensureProject(client, cfg);
          await ensureSession(client, cfg, ctx.sessionKey);
          const sequence = await nextSequenceNum(client, ctx.sessionKey);
          const role = readStringParam(params, "role") ?? "user";
          const metadata =
            (params.metadata as Record<string, string> | undefined) ?? undefined;

          const result = await client.post<Array<{ uid: string }>>("/memories", {
            session_key: ctx.sessionKey,
            episodes: [
              {
                uid: `${ctx.sessionKey}-${sequence}`,
                session_key: ctx.sessionKey,
                session_id: ctx.sessionKey,
                producer_id: cfg.userId ?? role,
                producer_role: role,
                sequence_num: sequence,
                content: normalizedText,
                filterable_metadata_json: JSON.stringify(
                  toMetadata(metadata, {
                    run_id: ctx.sessionKey,
                    user_id: cfg.userId,
                  }),
                ),
              },
            ],
          });
          return withExecutionEnvelope(toolName, ctx, { result });
        });
      },
    }));

    registerToolAliases(api, ["memory_get", "memolite_get"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Get",
      description: "Fetch a MemoLite memory by ID.",
      parameters: MemoryGetSchema,
      async execute(_toolCallId: string, params: Record<string, unknown>) {
        return executeSafely(api, toolName, ctx, async () => {
          const id = readStringParam(params, "id", { required: true })!;
          const result = await client.get<Record<string, unknown> | null>(
            `/memories/${encodeURIComponent(id)}`,
          );
          return withExecutionEnvelope(toolName, ctx, { result });
        });
      },
    }));

    registerToolAliases(api, ["memory_list", "memolite_list"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory List",
      description: "List MemoLite memories by scope: session | all.",
      parameters: MemoryListSchema,
      async execute(_toolCallId: string, params: Record<string, unknown>) {
        return executeSafely(api, toolName, ctx, async () => {
          const scope = normalizeScope(params.scope, "session");
          const pageSize = readNumberParam(params, "pageSize") ?? DEFAULT_PAGE_SIZE;
          const pageNum = readNumberParam(params, "pageNum") ?? 0;
          const result = await listMemories({
            client,
            scope,
            sessionKey: ctx.sessionKey,
            cfg,
            pageSize,
            pageNum,
          });
          return withExecutionEnvelope(toolName, ctx, {
            scope,
            pageSize,
            pageNum,
            result,
          });
        });
      },
    }));

    registerToolAliases(api, ["memory_forget", "memolite_forget"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Forget",
      description: "Forget a MemoLite memory by ID or query.",
      parameters: MemoryForgetSchema,
      async execute(_toolCallId: string, params: Record<string, unknown>) {
        return executeSafely(api, toolName, ctx, async () => {
          const memoryId = readStringParam(params, "memoryId");
          const rawQuery = readStringParam(params, "query");
          const explicitScope =
            params.scope === "session" || params.scope === "all"
              ? (params.scope as MemoryScope)
              : undefined;
          const minScore =
            readNumberParam(params, "minScore") ?? DEFAULT_FORGET_THRESHOLD;

          if (memoryId) {
            await client.delete("/memories/episodes", { episode_uids: [memoryId] });
            return withExecutionEnvelope(toolName, ctx, {
              action: "forget",
              memoryId,
            });
          }
          if (!rawQuery) {
            return { error: "Provide memoryId or query" };
          }

          const { scope, query } = resolveQueryScope(rawQuery, explicitScope, "session");
          const result = await searchMemories({
            client,
            query,
            scope,
            sessionKey: ctx.sessionKey,
            cfg,
            limit: cfg.topK ?? DEFAULT_TOP_K,
            minScore,
          });
          const matches = result.episodic_matches
            .filter((match) => match.score >= minScore)
            .sort((left, right) => right.score - left.score);

          if (matches.length === 0) {
            return withExecutionEnvelope(toolName, ctx, {
              action: "search",
              found: 0,
            });
          }
          const [best, second] = matches;
          if (best && (!second || second.score < minScore)) {
            await client.delete("/memories/episodes", {
              episode_uids: [best.episode.uid],
            });
            return withExecutionEnvelope(toolName, ctx, {
              action: "auto-delete",
              memoryId: best.episode.uid,
              score: best.score,
            });
          }
          return withExecutionEnvelope(toolName, ctx, {
            action: "candidates",
            candidates: matches.slice(0, 5).map((match) => ({
              uid: match.episode.uid,
              content: match.episode.content,
              score: match.score,
            })),
          });
        });
      },
    }));

    registerToolAliases(api, ["memolite_status"], (ctx, toolName) => ({
      name: toolName,
      label: "MemoLite Status",
      description: "Verify that the OpenClaw MemoLite plugin is the active provider and can reach the backend service.",
      parameters: MemoryStatusSchema,
      async execute() {
        return executeSafely(api, toolName, ctx, async () => {
          const health = await client.health();
          return withExecutionEnvelope(toolName, ctx, {
            health,
            config: {
              baseUrl: cfg.baseUrl ?? DEFAULT_BASE_URL,
              orgId: cfg.orgId ?? null,
              projectId: cfg.projectId ?? null,
              userId: cfg.userId ?? null,
              autoCapture: cfg.autoCapture ?? false,
              autoRecall: cfg.autoRecall ?? false,
              searchThreshold: cfg.searchThreshold ?? DEFAULT_SEARCH_THRESHOLD,
              topK: cfg.topK ?? DEFAULT_TOP_K,
            },
            toolAliases: [
              "memory_search",
              "memolite_search",
              "memory_store",
              "memolite_store",
              "memory_get",
              "memolite_get",
              "memory_list",
              "memolite_list",
              "memory_forget",
              "memolite_forget",
              "memolite_status",
            ],
          });
        });
      },
    }));

    if (cfg.autoRecall) {
      api.on("before_agent_start", async (event, ctx) => {
        if (!event.prompt || typeof event.prompt !== "string" || event.prompt.trim().length < 3) {
          return undefined;
        }
        try {
          const { scope, query } = resolveQueryScope(event.prompt, undefined, "session");
          const result = await searchMemories({
            client,
            query,
            scope,
            sessionKey: ctx.sessionKey,
            cfg,
            limit: cfg.topK ?? DEFAULT_TOP_K,
            minScore: cfg.searchThreshold ?? DEFAULT_SEARCH_THRESHOLD,
          });
          if (result.episodic_matches.length === 0 && !(result.semantic_features ?? []).length) {
            return undefined;
          }
          return {
            prependContext:
              `<relevant-memories>\n` +
              `The following memories may be relevant to this conversation:\n` +
              `${formatRecallContext(result, cfg.topK ?? DEFAULT_TOP_K)}\n` +
              `</relevant-memories>`,
          };
        } catch (error) {
          api.logger.warn(`openclaw-memolite: recall failed: ${String(error)}`);
          return undefined;
        }
      });
    }

    if (cfg.autoCapture) {
      api.on("agent_end", async (event, ctx) => {
        if (!event.success || !Array.isArray(event.messages) || event.messages.length === 0) {
          return;
        }
        try {
          await autoCaptureMessages({
            api,
            client,
            cfg,
            sessionKey: ctx.sessionKey,
            messages: event.messages,
          });
        } catch (error) {
          api.logger.warn(`openclaw-memolite: capture failed: ${String(error)}`);
        }
      });
    }

    api.registerService({
      id: "openclaw-memolite",
      start: () => api.logger.info("openclaw-memolite: initialized"),
      stop: () => api.logger.info("openclaw-memolite: stopped"),
    });
  },
};

export default memlitePlugin;
