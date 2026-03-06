import type { MemLiteClient } from "./client";
import type {
  AgentModeResponse,
  EpisodeResponse,
  MemoryAddInput,
  MemorySearchInput,
  MemorySearchResponse,
} from "./types";

export class MemLiteMemoryApi {
  constructor(private readonly client: MemLiteClient) {}

  async add(input: MemoryAddInput): Promise<string[]> {
    const response = await this.client.request<Array<{ uid: string }>>("POST", "/memories", {
      body: {
        session_key: input.sessionKey,
        semantic_set_id: input.semanticSetId ?? null,
        episodes: input.episodes,
      },
    });
    return response.map((item) => item.uid);
  }

  async search(input: MemorySearchInput): Promise<MemorySearchResponse> {
    return this.client.request<MemorySearchResponse>("POST", "/memories/search", {
      body: {
        query: input.query,
        session_key: input.sessionKey,
        session_id: input.sessionId,
        semantic_set_id: input.semanticSetId ?? null,
        mode: input.mode ?? "auto",
        limit: input.limit ?? 5,
        context_window: input.contextWindow ?? 1,
        min_score: input.minScore ?? 0.0001,
        producer_role: input.producerRole,
        episode_type: input.episodeType,
      },
    });
  }

  async agent(input: MemorySearchInput): Promise<AgentModeResponse> {
    return this.client.request<AgentModeResponse>("POST", "/memories/agent", {
      body: {
        query: input.query,
        session_key: input.sessionKey,
        session_id: input.sessionId,
        semantic_set_id: input.semanticSetId ?? null,
        mode: input.mode ?? "auto",
        limit: input.limit ?? 5,
        context_window: input.contextWindow ?? 1,
      },
    });
  }

  async list(input: { sessionKey: string }): Promise<EpisodeResponse[]> {
    return this.client.request<EpisodeResponse[]>("GET", "/memories", {
      query: {
        session_key: input.sessionKey,
      },
    });
  }

  async deleteEpisodes(input: {
    episodeUids: string[];
    semanticSetId?: string | null;
  }): Promise<void> {
    await this.client.request("DELETE", "/memories/episodes", {
      body: {
        episode_uids: input.episodeUids,
        semantic_set_id: input.semanticSetId ?? null,
      },
    });
  }
}
