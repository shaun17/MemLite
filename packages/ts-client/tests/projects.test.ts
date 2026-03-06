import { describe, expect, it, vi } from "vitest";

import { MemLiteClient } from "../src";

describe("project api", () => {
  it("supports project CRUD calls", async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            org_id: "org-a",
            project_id: "project-a",
            description: "demo",
            created_at: "2026-03-06T00:00:00Z",
            updated_at: "2026-03-06T00:00:00Z",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              org_id: "org-a",
              project_id: "project-a",
              description: "demo",
              created_at: "2026-03-06T00:00:00Z",
              updated_at: "2026-03-06T00:00:00Z",
            },
          ]),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ count: 3 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const client = new MemLiteClient({ baseUrl: "http://testserver", fetchImpl });

    await client.projects.create({ orgId: "org-a", projectId: "project-a" });
    const project = await client.projects.get({ orgId: "org-a", projectId: "project-a" });
    const projects = await client.projects.list({ orgId: "org-a" });
    const count = await client.projects.episodeCount({
      orgId: "org-a",
      projectId: "project-a",
    });
    await client.projects.delete({ orgId: "org-a", projectId: "project-a" });

    expect(project.project_id).toBe("project-a");
    expect(projects).toHaveLength(1);
    expect(count).toBe(3);
  });
});
