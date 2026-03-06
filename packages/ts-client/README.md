# `@memlite/ts-client`

MemLite 的 TypeScript SDK。

## Quickstart

```ts
import { MemLiteClient } from "@memlite/ts-client";

const client = new MemLiteClient({ baseUrl: "http://127.0.0.1:8080" });

await client.projects.create({ orgId: "demo-org", projectId: "demo-project" });
const projects = await client.projects.list({ orgId: "demo-org" });
console.log(projects);
```
