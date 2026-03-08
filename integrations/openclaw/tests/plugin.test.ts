import { describe, expect, it, vi } from "vitest";

import plugin from "../src/index";

type RegisteredTool = ReturnType<(typeof plugin)["register"]> | {
  name?: string;
  execute?: (toolCallId: string, params: Record<string, unknown>) => Promise<unknown>;
};

function createApi(config: Record<string, unknown> = {}) {
  const tools: Array<any> = [];
  const hooks = new Map<string, (event: any, ctx: { sessionKey?: string }) => Promise<unknown>>();
  const logger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };
  const api = {
    pluginConfig: config,
    logger,
    registerTool(factory: (ctx: { sessionKey?: string }) => unknown) {
      tools.push(factory({ sessionKey: "session-a" }));
    },
    registerService: vi.fn(),
    on(event: string, handler: (event: any, ctx: { sessionKey?: string }) => Promise<unknown>) {
      hooks.set(event, handler);
    },
  };
  plugin.register(api as any);
  return { api, tools, hooks, logger };
}

describe("openclaw memolite plugin", () => {
  it("registers all memory tools", () => {
    const { tools } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
    });

    expect(tools.map((tool) => tool.name)).toEqual([
      "memory_search",
      "memory_store",
      "memory_get",
      "memory_list",
      "memory_forget",
    ]);
  });

  it("stores and searches memory through the REST API", async () => {
    global.fetch = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "missing" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "missing" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ uid: "session-a-1" }]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            episodic_matches: [
              {
                episode: {
                  uid: "session-a-1",
                  session_key: "session-a",
                  session_id: "session-a",
                  content: "Ramen is my favorite food.",
                  producer_role: "user",
                  sequence_num: 1,
                },
                score: 0.91,
              },
            ],
            semantic_features: [],
          }),
          { status: 200 },
        ),
      );

    const { tools } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
    });

    const storeResult = await tools[1].execute("tool-1", { text: "Ramen is my favorite food." });
    const searchResult = await tools[0].execute("tool-2", { query: "favorite food" });

    expect(storeResult).toEqual({ result: [{ uid: "session-a-1" }] });
    expect((searchResult as any).result.episodic_matches[0].episode.uid).toBe("session-a-1");
  });

  it("gets, lists and forgets memory", async () => {
    global.fetch = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            uid: "ep-1",
            session_key: "session-a",
            session_id: "session-a",
            content: "Ramen is my favorite food.",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ session_key: "session-a" }, { session_key: "session-b" }]), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([{ uid: "ep-1" }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ uid: "ep-2" }]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const { tools } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
    });

    const getResult = await tools[2].execute("tool-1", { id: "ep-1" });
    const listResult = await tools[3].execute("tool-2", { scope: "all", pageSize: 10, pageNum: 0 });
    const forgetResult = await tools[4].execute("tool-3", { memoryId: "ep-1" });

    expect((getResult as any).result.uid).toBe("ep-1");
    expect((listResult as any).result).toHaveLength(2);
    expect(forgetResult).toEqual({ action: "forget", memoryId: "ep-1" });
  });

  it("auto-recalls and auto-captures through hooks", async () => {
    global.fetch = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            episodic_matches: [
              {
                episode: {
                  uid: "ep-1",
                  session_key: "session-a",
                  session_id: "session-a",
                  content: "User likes ramen.",
                  producer_role: "user",
                  sequence_num: 1,
                },
                score: 0.93,
              },
            ],
            semantic_features: [],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "missing" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "missing" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ uid: "session-a-1" }]), { status: 200 }));

    const { hooks, logger } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
      autoRecall: true,
      autoCapture: true,
    });

    const recall = await hooks.get("before_agent_start")?.(
      { prompt: "What food do I like?" },
      { sessionKey: "session-a" },
    );
    await hooks.get("agent_end")?.(
      {
        success: true,
        messages: [{ role: "user", content: "Remember I like ramen." }],
      },
      { sessionKey: "session-a" },
    );

    expect((recall as any).prependContext).toContain("User likes ramen.");
    expect(logger.info).toHaveBeenCalledWith("openclaw-memolite: auto-capture completed");
  });

  it("captures first and recalls on the next hook cycle", async () => {
    global.fetch = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "missing" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "missing" }), { status: 404 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ uid: "session-a-1" }]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            episodic_matches: [
              {
                episode: {
                  uid: "session-a-1",
                  session_key: "session-a",
                  session_id: "session-a",
                  content: "Remember I like ramen.",
                  producer_role: "user",
                  sequence_num: 1,
                },
                score: 0.95,
              },
            ],
            semantic_features: [],
          }),
          { status: 200 },
        ),
      );

    const { hooks } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
      autoRecall: true,
      autoCapture: true,
    });

    await hooks.get("agent_end")?.(
      {
        success: true,
        messages: [{ role: "user", content: "Remember I like ramen." }],
      },
      { sessionKey: "session-a" },
    );
    const recall = await hooks.get("before_agent_start")?.(
      { prompt: "What do I like to eat?" },
      { sessionKey: "session-a" },
    );

    expect((recall as any).prependContext).toContain("Remember I like ramen.");
  });

  it("defaults memory_search scope to session", async () => {
    global.fetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ episodic_matches: [], semantic_features: [] }), {
        status: 200,
      }),
    );

    const { tools } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
    });

    await tools[0].execute("tool-1", { query: "我喜欢什么" });

    const call = (global.fetch as any).mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.session_id).toBe("session-a");
  });

  it("switches to scope=all when query asks for all memories", async () => {
    global.fetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ episodic_matches: [], semantic_features: [] }), {
        status: 200,
      }),
    );

    const { tools } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
    });

    await tools[0].execute("tool-1", { query: "查询全部信息：我喜欢什么" });

    const call = (global.fetch as any).mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.session_id).toBeNull();
  });

  it("returns readable errors for tool failures", async () => {
    global.fetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    );

    const { tools, logger } = createApi({
      baseUrl: "http://memlite.local",
      orgId: "org-a",
      projectId: "project-a",
      userId: "user-1",
    });

    const result = await tools[0].execute("tool-1", { query: "food" });

    expect(result).toEqual({ error: '500: {"detail":"boom"}' });
    expect(logger.warn).toHaveBeenCalled();
  });
});
