import type { MemLiteClient } from "./client";
import type { ProjectCreateInput, ProjectListInput, ProjectResponse } from "./types";

export class MemLiteProjectApi {
  constructor(private readonly client: MemLiteClient) {}

  async create(input: ProjectCreateInput): Promise<void> {
    await this.client.request("POST", "/projects", {
      body: {
        org_id: input.orgId,
        project_id: input.projectId,
        description: input.description ?? null,
      },
    });
  }

  async get(input: { orgId: string; projectId: string }): Promise<ProjectResponse> {
    return this.client.request<ProjectResponse>(
      "GET",
      `/projects/${input.orgId}/${input.projectId}`,
    );
  }

  async list(input: ProjectListInput = {}): Promise<ProjectResponse[]> {
    return this.client.request<ProjectResponse[]>("GET", "/projects", {
      query: {
        org_id: input.orgId,
      },
    });
  }

  async delete(input: { orgId: string; projectId: string }): Promise<void> {
    await this.client.request("DELETE", `/projects/${input.orgId}/${input.projectId}`);
  }

  async episodeCount(input: { orgId: string; projectId: string }): Promise<number> {
    const response = await this.client.request<{ count: number }>(
      "GET",
      `/projects/${input.orgId}/${input.projectId}/episodes/count`,
    );
    return response.count;
  }
}
