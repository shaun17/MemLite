import { describe, expect, it, vi } from "vitest";

import { MemLiteClient, type EpisodeInput } from "../src";

describe("memory api", () => {
  it("supports memory add/search/list/delete calls", async () => {
    const episode: EpisodeInput = {
      uid: "ep-1",
      session_key: "session-a",
      session_id: "session-a",
      producer_id: "user-1",
      producer_role: "user",
      content: "Ramen is my favorite food.",
    };
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify([{ uid: "ep-1" }]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            mode: "mixed",
            rewritten_query: "favorite food",
            subqueries: ["favorite food"],
            episodic_matches: [],
            semantic_features: [],
            combined: [
              {
                source: "episodic",
                content: "Ramen is my favorite food.",
                identifier: "ep-1",
                score: 1,
              },
            ],
            expanded_context: [],
            short_term_context: "",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              uid: "ep-1",
              session_key: "session-a",
              session_id: "session-a",
              producer_id: "user-1",
              producer_role: "user",
              produced_for_id: null,
              sequence_num: 0,
              content: "Ramen is my favorite food.",
              content_type: "text",
              episode_type: "message",
              created_at: "2026-03-06T00:00:00Z",
              metadata_json: null,
              filterable_metadata_json: null,
              deleted: 0,
            },
          ]),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            search: {
              mode: "mixed",
              rewritten_query: "food",
              subqueries: ["food"],
              episodic_matches: [],
              semantic_features: [],
              combined: [
                {
                  source: "episodic",
                  content: "Ramen is my favorite food.",
                  identifier: "ep-1",
                  score: 1,
                },
              ],
              expanded_context: [],
              short_term_context: "",
            },
            context_text: "Ramen is my favorite food.",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const client = new MemLiteClient({ baseUrl: "http://testserver", fetchImpl });

    const ids = await client.memory.add({
      sessionKey: "session-a",
      semanticSetId: "session-a",
      episodes: [episode],
    });
    const search = await client.memory.search({
      query: "favorite food",
      sessionKey: "session-a",
      sessionId: "session-a",
      semanticSetId: "session-a",
      mode: "mixed",
    });
    const list = await client.memory.list({ sessionKey: "session-a" });
    const agent = await client.memory.agent({
      query: "food",
      sessionKey: "session-a",
      sessionId: "session-a",
      semanticSetId: "session-a",
      mode: "mixed",
    });
    await client.memory.deleteEpisodes({
      episodeUids: ["ep-1"],
      semanticSetId: "session-a",
    });

    expect(ids).toEqual(["ep-1"]);
    expect(search.combined[0]?.identifier).toBe("ep-1");
    expect(list[0]?.uid).toBe("ep-1");
    expect(agent.context_text).toContain("Ramen");
  });
});
