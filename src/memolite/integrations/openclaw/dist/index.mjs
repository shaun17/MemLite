// src/index.ts
var DEFAULT_BASE_URL = "http://127.0.0.1:18731";
var DEFAULT_TOP_K = 5;
var DEFAULT_SEARCH_THRESHOLD = 0.5;
var DEFAULT_FORGET_THRESHOLD = 0.85;
var DEFAULT_PAGE_SIZE = 10;
var MAX_CAPTURE_CHARS = 4e3;
var MAX_RECALL_LINE_CHARS = 500;
var MAX_RECALL_TOTAL_CHARS = 4e3;
var MAX_TOOL_RESULT_MATCHES = 20;
var MAX_TOOL_RESULT_CONTENT_CHARS = 1e3;
var PluginConfigJsonSchema = {
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
    topK: { type: "number" }
  },
  required: []
};
var MemorySearchSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    query: { type: "string" },
    scope: { type: "string", enum: ["session", "all"] },
    limit: { type: "number" },
    minScore: { type: "number" }
  },
  required: ["query"]
};
var MemoryStoreSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    text: { type: "string" },
    role: { type: "string", enum: ["user", "assistant", "system"] },
    metadata: { type: "object", additionalProperties: { type: "string" } }
  },
  required: ["text"]
};
var MemoryGetSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    id: { type: "string" }
  },
  required: ["id"]
};
var MemoryListSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    scope: { type: "string", enum: ["session", "all"] },
    pageSize: { type: "number" },
    pageNum: { type: "number" }
  },
  required: []
};
var MemoryForgetSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    memoryId: { type: "string" },
    query: { type: "string" },
    scope: { type: "string", enum: ["session", "all"] },
    minScore: { type: "number" }
  },
  required: []
};
var MemoryStatusSchema = {
  type: "object",
  additionalProperties: false,
  properties: {},
  required: []
};
var memoLiteApiClient = class {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }
  async get(path, query) {
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== void 0) {
        url.searchParams.set(key, String(value));
      }
    }
    const response = await fetch(url, { method: "GET" });
    return parseJson(response);
  }
  async post(path, body) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    return parseJson(response);
  }
  async patch(path, body) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    return parseJson(response);
  }
  async delete(path, body) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: { "content-type": "application/json" },
      body: body === void 0 ? void 0 : JSON.stringify(body)
    });
    return parseJson(response);
  }
  async health() {
    return this.get("/health");
  }
};
var parseJson = async (response) => {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(`${response.status}: ${JSON.stringify(payload)}`);
  }
  return payload;
};
function resolvePluginConfig(api) {
  const raw = api.pluginConfig ?? {};
  return {
    baseUrl: typeof raw.baseUrl === "string" ? raw.baseUrl.trim() : void 0,
    userId: typeof raw.userId === "string" ? raw.userId.trim() : void 0,
    orgId: typeof raw.orgId === "string" ? raw.orgId.trim() : void 0,
    projectId: typeof raw.projectId === "string" ? raw.projectId.trim() : void 0,
    autoCapture: typeof raw.autoCapture === "boolean" ? raw.autoCapture : void 0,
    autoRecall: typeof raw.autoRecall === "boolean" ? raw.autoRecall : void 0,
    searchThreshold: typeof raw.searchThreshold === "number" ? raw.searchThreshold : void 0,
    topK: typeof raw.topK === "number" ? raw.topK : void 0
  };
}
function requireProjectConfig(cfg) {
  if (!cfg.orgId || !cfg.projectId) {
    throw new Error("Missing orgId/projectId in plugin config.");
  }
  return { orgId: cfg.orgId, projectId: cfg.projectId };
}
function normalizeScope(value, fallback) {
  return value === "session" || value === "all" ? value : fallback;
}
function resolveQueryScope(rawQuery, explicitScope, fallback) {
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
  const globalPattern = /(查询全部|全部信息|所有信息|所有记忆|全部记忆|全局|跨会话|scope\s*=\s*all|all\s+memories|all\s+sessions)/i;
  if (globalPattern.test(query)) {
    return { scope: "all", query };
  }
  return { scope: fallback, query };
}
function readStringParam(params, name, options = {}) {
  const value = params[name];
  if (typeof value === "string" && value.length > 0) {
    return value;
  }
  if (options.required) {
    throw new Error(`Missing required string param: ${name}`);
  }
  return void 0;
}
function readNumberParam(params, name) {
  const value = params[name];
  return typeof value === "number" ? value : void 0;
}
function toMetadata(base, extras) {
  const merged = { ...base ?? {} };
  for (const [key, value] of Object.entries(extras)) {
    if (value) {
      merged[key] = value;
    }
  }
  return merged;
}
function resolveSemanticSetId(cfg, sessionKey) {
  return cfg.userId ?? sessionKey ?? null;
}
async function ensureProject(client, cfg) {
  const { orgId, projectId } = requireProjectConfig(cfg);
  try {
    await client.get(`/projects/${orgId}/${projectId}`);
  } catch {
    await client.post("/projects", {
      org_id: orgId,
      project_id: projectId
    });
  }
}
async function ensureSession(client, cfg, sessionKey) {
  const { orgId, projectId } = requireProjectConfig(cfg);
  try {
    await client.get(`/sessions/${encodeURIComponent(sessionKey)}`);
  } catch {
    await client.post("/sessions", {
      session_key: sessionKey,
      org_id: orgId,
      project_id: projectId,
      session_id: sessionKey,
      user_id: cfg.userId ?? null
    });
  }
}
async function nextSequenceNum(client, sessionKey) {
  const episodes = await client.get("/memories", {
    session_key: sessionKey
  });
  const maxSequence = episodes.reduce(
    (max, episode) => Math.max(max, episode.sequence_num),
    0
  );
  return maxSequence + 1;
}
async function searchMemories(params) {
  const { client, query, scope, sessionKey, cfg, limit, minScore } = params;
  return client.post("/memories/search", {
    query,
    session_key: sessionKey ?? null,
    session_id: scope === "session" ? sessionKey ?? null : null,
    semantic_set_id: resolveSemanticSetId(cfg, sessionKey),
    mode: "mixed",
    limit,
    min_score: minScore
  });
}
async function listMemories(params) {
  const { client, scope, sessionKey, cfg, pageSize, pageNum } = params;
  if (scope === "session") {
    if (!sessionKey) {
      return [];
    }
    const episodes = await client.get("/memories", {
      session_key: sessionKey
    });
    return episodes.slice(pageNum * pageSize, (pageNum + 1) * pageSize);
  }
  const sessions = await client.get("/sessions", {
    org_id: cfg.orgId,
    project_id: cfg.projectId,
    user_id: cfg.userId
  });
  const allEpisodes = (await Promise.all(
    sessions.map(
      (session) => client.get("/memories", {
        session_key: session.session_key
      })
    )
  )).flat();
  return allEpisodes.slice(pageNum * pageSize, (pageNum + 1) * pageSize);
}
function extractMessageTextBlocks(message) {
  const content = message.content;
  if (typeof content === "string") {
    return [content];
  }
  if (Array.isArray(content)) {
    return content.map((block) => {
      if (block && typeof block === "object") {
        const record = block;
        if (record.type === "text" && typeof record.text === "string") {
          return record.text;
        }
      }
      return null;
    }).filter((text) => Boolean(text));
  }
  return [];
}
function clipText(text, maxChars) {
  if (text.length <= maxChars) {
    return text;
  }
  return `${text.slice(0, maxChars)} \u2026[truncated ${text.length - maxChars} chars]`;
}
function formatRecallContext(result, limit) {
  const lines = [];
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
function compactSearchResult(result) {
  return {
    ...result,
    episodic_matches: (result.episodic_matches ?? []).slice(0, MAX_TOOL_RESULT_MATCHES).map((m) => ({
      ...m,
      episode: {
        ...m.episode,
        content: clipText(m.episode.content, MAX_TOOL_RESULT_CONTENT_CHARS)
      }
    })),
    semantic_features: (result.semantic_features ?? []).slice(0, MAX_TOOL_RESULT_MATCHES).map((f) => ({
      ...f,
      value: clipText(f.value, MAX_TOOL_RESULT_CONTENT_CHARS)
    }))
  };
}
async function autoCaptureMessages(params) {
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
    const record = message;
    const role = typeof record.role === "string" ? record.role : "user";
    const blocks = extractMessageTextBlocks(record);
    for (const text of blocks) {
      if (text.trim().length < 5 || text.includes("relevant-memories")) {
        continue;
      }
      const normalizedText = clipText(text, MAX_CAPTURE_CHARS);
      await client.post("/memories", {
        session_key: sessionKey,
        semantic_set_id: resolveSemanticSetId(cfg, sessionKey),
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
              toMetadata(void 0, {
                run_id: sessionKey,
                user_id: cfg.userId
              })
            )
          }
        ]
      });
      sequence += 1;
    }
  }
  api.logger.info("openclaw-memolite: auto-capture completed");
}
async function executeSafely(api, operation, ctx, callback) {
  api.logger.info(
    `openclaw-memolite: ${operation} invoked session=${ctx.sessionKey ?? "none"}`
  );
  try {
    const result = await callback();
    api.logger.info(
      `openclaw-memolite: ${operation} succeeded session=${ctx.sessionKey ?? "none"}`
    );
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    api.logger.warn(`openclaw-memolite: ${operation} failed: ${message}`);
    return { error: message };
  }
}
function withExecutionEnvelope(toolName, ctx, data) {
  return {
    provider: "memolite",
    pluginId: "openclaw-memolite",
    tool: toolName,
    executed: true,
    sessionKey: ctx.sessionKey ?? null,
    data
  };
}
function registerToolAliases(api, names, factory) {
  for (const name of names) {
    api.registerTool((ctx) => factory(ctx, name), { name });
  }
}
var memlitePlugin = {
  id: "openclaw-memolite",
  name: "MemoLite",
  description: "memoLite-backed memory tools with auto recall/capture",
  kind: "memory",
  configSchema: {
    jsonSchema: PluginConfigJsonSchema
  },
  register(api) {
    const cfg = resolvePluginConfig(api);
    const client = new memoLiteApiClient(cfg.baseUrl ?? DEFAULT_BASE_URL);
    registerToolAliases(api, ["memory_search", "memolite_search"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Search",
      description: "Search MemoLite memories with scope: session | all.",
      parameters: MemorySearchSchema,
      async execute(_toolCallId, params) {
        return executeSafely(api, toolName, ctx, async () => {
          const rawQuery = readStringParam(params, "query", { required: true });
          const explicitScope = params.scope === "session" || params.scope === "all" ? params.scope : void 0;
          const { scope, query } = resolveQueryScope(rawQuery, explicitScope, "session");
          const limit = readNumberParam(params, "limit") ?? cfg.topK ?? DEFAULT_TOP_K;
          const minScore = readNumberParam(params, "minScore") ?? cfg.searchThreshold ?? DEFAULT_SEARCH_THRESHOLD;
          const result = await searchMemories({
            client,
            query,
            scope,
            sessionKey: ctx.sessionKey,
            cfg,
            limit,
            minScore
          });
          return withExecutionEnvelope(toolName, ctx, {
            scope,
            result: compactSearchResult(result)
          });
        });
      }
    }));
    registerToolAliases(api, ["memory_store", "memolite_store"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Store",
      description: "Store an episodic MemoLite memory in the current session.",
      parameters: MemoryStoreSchema,
      async execute(_toolCallId, params) {
        return executeSafely(api, toolName, ctx, async () => {
          const text = readStringParam(params, "text", { required: true });
          const normalizedText = clipText(text, MAX_CAPTURE_CHARS);
          if (!ctx.sessionKey) {
            return { error: `No active session for ${toolName}` };
          }
          await ensureProject(client, cfg);
          await ensureSession(client, cfg, ctx.sessionKey);
          const sequence = await nextSequenceNum(client, ctx.sessionKey);
          const role = readStringParam(params, "role") ?? "user";
          const metadata = params.metadata ?? void 0;
          const result = await client.post("/memories", {
            session_key: ctx.sessionKey,
            semantic_set_id: resolveSemanticSetId(cfg, ctx.sessionKey),
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
                    user_id: cfg.userId
                  })
                )
              }
            ]
          });
          return withExecutionEnvelope(toolName, ctx, { result });
        });
      }
    }));
    registerToolAliases(api, ["memory_get", "memolite_get"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Get",
      description: "Fetch a MemoLite memory by ID.",
      parameters: MemoryGetSchema,
      async execute(_toolCallId, params) {
        return executeSafely(api, toolName, ctx, async () => {
          const id = readStringParam(params, "id", { required: true });
          const result = await client.get(
            `/memories/${encodeURIComponent(id)}`
          );
          return withExecutionEnvelope(toolName, ctx, { result });
        });
      }
    }));
    registerToolAliases(api, ["memory_list", "memolite_list"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory List",
      description: "List MemoLite memories by scope: session | all.",
      parameters: MemoryListSchema,
      async execute(_toolCallId, params) {
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
            pageNum
          });
          return withExecutionEnvelope(toolName, ctx, {
            scope,
            pageSize,
            pageNum,
            result
          });
        });
      }
    }));
    registerToolAliases(api, ["memory_forget", "memolite_forget"], (ctx, toolName) => ({
      name: toolName,
      label: "Memory Forget",
      description: "Forget a MemoLite memory by ID or query.",
      parameters: MemoryForgetSchema,
      async execute(_toolCallId, params) {
        return executeSafely(api, toolName, ctx, async () => {
          const memoryId = readStringParam(params, "memoryId");
          const rawQuery = readStringParam(params, "query");
          const explicitScope = params.scope === "session" || params.scope === "all" ? params.scope : void 0;
          const minScore = readNumberParam(params, "minScore") ?? DEFAULT_FORGET_THRESHOLD;
          if (memoryId) {
            await client.delete("/memories/episodes", { episode_uids: [memoryId] });
            return withExecutionEnvelope(toolName, ctx, {
              action: "forget",
              memoryId
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
            minScore
          });
          const matches = result.episodic_matches.filter((match) => match.score >= minScore).sort((left, right) => right.score - left.score);
          if (matches.length === 0) {
            return withExecutionEnvelope(toolName, ctx, {
              action: "search",
              found: 0
            });
          }
          const [best, second] = matches;
          if (best && (!second || second.score < minScore)) {
            await client.delete("/memories/episodes", {
              episode_uids: [best.episode.uid]
            });
            return withExecutionEnvelope(toolName, ctx, {
              action: "auto-delete",
              memoryId: best.episode.uid,
              score: best.score
            });
          }
          return withExecutionEnvelope(toolName, ctx, {
            action: "candidates",
            candidates: matches.slice(0, 5).map((match) => ({
              uid: match.episode.uid,
              content: match.episode.content,
              score: match.score
            }))
          });
        });
      }
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
              topK: cfg.topK ?? DEFAULT_TOP_K
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
              "memolite_status"
            ]
          });
        });
      }
    }));
    if (cfg.autoRecall) {
      api.on("before_agent_start", async (event, ctx) => {
        if (!event.prompt || typeof event.prompt !== "string" || event.prompt.trim().length < 3) {
          return void 0;
        }
        try {
          const { scope, query } = resolveQueryScope(event.prompt, void 0, "session");
          const result = await searchMemories({
            client,
            query,
            scope,
            sessionKey: ctx.sessionKey,
            cfg,
            limit: cfg.topK ?? DEFAULT_TOP_K,
            minScore: cfg.searchThreshold ?? DEFAULT_SEARCH_THRESHOLD
          });
          if (result.episodic_matches.length === 0 && !(result.semantic_features ?? []).length) {
            return void 0;
          }
          return {
            prependContext: `<relevant-memories>
The following memories may be relevant to this conversation:
${formatRecallContext(result, cfg.topK ?? DEFAULT_TOP_K)}
</relevant-memories>`
          };
        } catch (error) {
          api.logger.warn(`openclaw-memolite: recall failed: ${String(error)}`);
          return void 0;
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
            messages: event.messages
          });
        } catch (error) {
          api.logger.warn(`openclaw-memolite: capture failed: ${String(error)}`);
        }
      });
    }
    api.registerService({
      id: "openclaw-memolite",
      start: () => api.logger.info("openclaw-memolite: initialized"),
      stop: () => api.logger.info("openclaw-memolite: stopped")
    });
  }
};
var index_default = memlitePlugin;
export {
  index_default as default
};
//# sourceMappingURL=index.mjs.map