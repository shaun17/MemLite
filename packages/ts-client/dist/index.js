// src/errors.ts
var MemLiteClientError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "MemLiteClientError";
  }
};
var MemLiteApiError = class extends MemLiteClientError {
  statusCode;
  responseBody;
  constructor(message, statusCode, responseBody) {
    super(message);
    this.name = "MemLiteApiError";
    this.statusCode = statusCode;
    this.responseBody = responseBody;
  }
};

// src/memory.ts
var MemLiteMemoryApi = class {
  constructor(client) {
    this.client = client;
  }
  async add(input) {
    const response = await this.client.request("POST", "/memories", {
      body: {
        session_key: input.sessionKey,
        semantic_set_id: input.semanticSetId ?? null,
        episodes: input.episodes
      }
    });
    return response.map((item) => item.uid);
  }
  async search(input) {
    return this.client.request("POST", "/memories/search", {
      body: {
        query: input.query,
        session_key: input.sessionKey,
        session_id: input.sessionId,
        semantic_set_id: input.semanticSetId ?? null,
        mode: input.mode ?? "auto",
        limit: input.limit ?? 5,
        context_window: input.contextWindow ?? 1,
        min_score: input.minScore ?? 1e-4,
        producer_role: input.producerRole,
        episode_type: input.episodeType
      }
    });
  }
  async agent(input) {
    return this.client.request("POST", "/memories/agent", {
      body: {
        query: input.query,
        session_key: input.sessionKey,
        session_id: input.sessionId,
        semantic_set_id: input.semanticSetId ?? null,
        mode: input.mode ?? "auto",
        limit: input.limit ?? 5,
        context_window: input.contextWindow ?? 1
      }
    });
  }
  async list(input) {
    return this.client.request("GET", "/memories", {
      query: {
        session_key: input.sessionKey
      }
    });
  }
  async deleteEpisodes(input) {
    await this.client.request("DELETE", "/memories/episodes", {
      body: {
        episode_uids: input.episodeUids,
        semantic_set_id: input.semanticSetId ?? null
      }
    });
  }
};

// src/projects.ts
var MemLiteProjectApi = class {
  constructor(client) {
    this.client = client;
  }
  async create(input) {
    await this.client.request("POST", "/projects", {
      body: {
        org_id: input.orgId,
        project_id: input.projectId,
        description: input.description ?? null
      }
    });
  }
  async get(input) {
    return this.client.request(
      "GET",
      `/projects/${input.orgId}/${input.projectId}`
    );
  }
  async list(input = {}) {
    return this.client.request("GET", "/projects", {
      query: {
        org_id: input.orgId
      }
    });
  }
  async delete(input) {
    await this.client.request("DELETE", `/projects/${input.orgId}/${input.projectId}`);
  }
  async episodeCount(input) {
    const response = await this.client.request(
      "GET",
      `/projects/${input.orgId}/${input.projectId}/episodes/count`
    );
    return response.count;
  }
};

// src/client.ts
var MemLiteClient = class {
  baseUrl;
  projects;
  memory;
  retries;
  retryBackoffMs;
  fetchImpl;
  headers;
  constructor(options) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.retries = options.retries ?? 2;
    this.retryBackoffMs = options.retryBackoffMs ?? 50;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.headers = options.headers ?? {};
    this.projects = new MemLiteProjectApi(this);
    this.memory = new MemLiteMemoryApi(this);
  }
  async request(method, path, options = {}) {
    let lastError = null;
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== void 0 && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
    for (let attempt = 0; attempt <= this.retries; attempt += 1) {
      try {
        const response = await this.fetchImpl(url, {
          method,
          headers: {
            "content-type": "application/json",
            ...this.headers
          },
          body: options.body === void 0 ? void 0 : JSON.stringify(options.body)
        });
        const payload = await decodeResponse(response);
        if (response.status >= 500 && attempt < this.retries) {
          await sleep(this.retryBackoffMs * (attempt + 1));
          continue;
        }
        if (!response.ok) {
          throw new MemLiteApiError(
            `${method.toUpperCase()} ${path} failed`,
            response.status,
            payload
          );
        }
        return payload;
      } catch (error) {
        lastError = error;
        if (error instanceof MemLiteApiError) {
          if (error.statusCode >= 500 && attempt < this.retries) {
            await sleep(this.retryBackoffMs * (attempt + 1));
            continue;
          }
          throw error;
        }
        if (attempt >= this.retries) {
          throw new MemLiteClientError(lastError.message);
        }
        await sleep(this.retryBackoffMs * (attempt + 1));
      }
    }
    throw new MemLiteClientError(lastError?.message ?? "request failed");
  }
};
var sleep = async (ms) => new Promise((resolve) => {
  setTimeout(resolve, ms);
});
var decodeResponse = async (response) => {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};
export {
  MemLiteApiError,
  MemLiteClient,
  MemLiteClientError
};
//# sourceMappingURL=index.js.map