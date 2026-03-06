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

const DEFAULT_BASE_URL = "http://127.0.0.1:8080";
const DEFAULT_TOP_K = 5;
const DEFAULT_SEARCH_THRESHOLD = 0.5;
const DEFAULT_FORGET_THRESHOLD = 0.85;
const DEFAULT_PAGE_SIZE = 10;

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

class MemLiteApiClient {
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

async function ensureProject(client: MemLiteApiClient, cfg: PluginConfig): Promise<void> {
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
  client: MemLiteApiClient,
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

async function nextSequenceNum(client: MemLiteApiClient, sessionKey: string): Promise<number> {
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
  client: MemLiteApiClient;
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
  client: MemLiteApiClient;
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

function formatRecallContext(result: MemorySearchResponse, limit: number): string {
  const lines: string[] = [];
  for (const match of result.episodic_matches.slice(0, limit)) {
    lines.push(`- [episodic] ${match.episode.content} (${match.score.toFixed(2)})`);
  }
  for (const feature of result.semantic_features ?? []) {
    if (lines.length >= limit) {
      break;
    }
    lines.push(`- [semantic] ${feature.feature_name}: ${feature.value}`);
  }
  return lines.join("\n");
}

async function autoCaptureMessages(params: {
  api: OpenClawPluginApi;
  client: MemLiteApiClient;
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
            content: text,
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
  api.logger.info("openclaw-memlite: auto-capture completed");
}

async function executeSafely<T>(
  api: OpenClawPluginApi,
  operation: string,
  callback: () => Promise<T>,
): Promise<T | { error: string }> {
  try {
    return await callback();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    api.logger.warn(`openclaw-memlite: ${operation} failed: ${message}`);
    return { error: message };
  }
}

const memlitePlugin = {
  id: "openclaw-memlite",
  name: "MemLite",
  description: "MemLite-backed memory tools with auto recall/capture",
  kind: "memory" as const,
  configSchema: {
    jsonSchema: PluginConfigJsonSchema,
  },
  register(api: OpenClawPluginApi) {
    const cfg = resolvePluginConfig(api);
    const client = new MemLiteApiClient(cfg.baseUrl ?? DEFAULT_BASE_URL);

    api.registerTool(
      (ctx) => ({
        name: "memory_search",
        label: "Memory Search",
        description: "Search memories with scope: session | all.",
        parameters: MemorySearchSchema,
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          return executeSafely(api, "memory_search", async () => {
            const query = readStringParam(params, "query", { required: true })!;
            const scope = normalizeScope(params.scope, "all");
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
            return { scope, result };
          });
        },
      }),
      { name: "memory_search" },
    );

    api.registerTool(
      (ctx) => ({
        name: "memory_store",
        label: "Memory Store",
        description: "Store an episodic memory in the current session.",
        parameters: MemoryStoreSchema,
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          return executeSafely(api, "memory_store", async () => {
            const text = readStringParam(params, "text", { required: true })!;
            if (!ctx.sessionKey) {
              return { error: "No active session for memory_store" };
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
                  content: text,
                  filterable_metadata_json: JSON.stringify(
                    toMetadata(metadata, {
                      run_id: ctx.sessionKey,
                      user_id: cfg.userId,
                    }),
                  ),
                },
              ],
            });
            return { result };
          });
        },
      }),
      { name: "memory_store" },
    );

    api.registerTool(
      (ctx) => ({
        name: "memory_get",
        label: "Memory Get",
        description: "Fetch memory by ID.",
        parameters: MemoryGetSchema,
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          return executeSafely(api, "memory_get", async () => {
            const id = readStringParam(params, "id", { required: true })!;
            const result = await client.get<Record<string, unknown> | null>(
              `/memories/${encodeURIComponent(id)}`,
            );
            return { sessionKey: ctx.sessionKey, result };
          });
        },
      }),
      { name: "memory_get" },
    );

    api.registerTool(
      (ctx) => ({
        name: "memory_list",
        label: "Memory List",
        description: "List memories by scope: session | all.",
        parameters: MemoryListSchema,
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          return executeSafely(api, "memory_list", async () => {
            const scope = normalizeScope(params.scope, "all");
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
            return { scope, pageSize, pageNum, result };
          });
        },
      }),
      { name: "memory_list" },
    );

    api.registerTool(
      (ctx) => ({
        name: "memory_forget",
        label: "Memory Forget",
        description: "Forget memory by ID or query.",
        parameters: MemoryForgetSchema,
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          return executeSafely(api, "memory_forget", async () => {
            const memoryId = readStringParam(params, "memoryId");
            const query = readStringParam(params, "query");
            const scope = normalizeScope(params.scope, "all");
            const minScore =
              readNumberParam(params, "minScore") ?? DEFAULT_FORGET_THRESHOLD;

            if (memoryId) {
              await client.delete("/memories/episodes", { episode_uids: [memoryId] });
              return { action: "forget", memoryId };
            }
            if (!query) {
              return { error: "Provide memoryId or query" };
            }

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
              return { action: "search", found: 0 };
            }
            const [best, second] = matches;
            if (best && (!second || second.score < minScore)) {
              await client.delete("/memories/episodes", {
                episode_uids: [best.episode.uid],
              });
              return { action: "auto-delete", memoryId: best.episode.uid, score: best.score };
            }
            return {
              action: "candidates",
              candidates: matches.slice(0, 5).map((match) => ({
                uid: match.episode.uid,
                content: match.episode.content,
                score: match.score,
              })),
            };
          });
        },
      }),
      { name: "memory_forget" },
    );

    if (cfg.autoRecall) {
      api.on("before_agent_start", async (event, ctx) => {
        if (!event.prompt || typeof event.prompt !== "string" || event.prompt.trim().length < 3) {
          return undefined;
        }
        try {
          const result = await searchMemories({
            client,
            query: event.prompt,
            scope: "all",
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
          api.logger.warn(`openclaw-memlite: recall failed: ${String(error)}`);
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
          api.logger.warn(`openclaw-memlite: capture failed: ${String(error)}`);
        }
      });
    }

    api.registerService({
      id: "openclaw-memlite",
      start: () => api.logger.info("openclaw-memlite: initialized"),
      stop: () => api.logger.info("openclaw-memlite: stopped"),
    });
  },
};

export default memlitePlugin;
