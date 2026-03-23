# memoLite

> 中文版本: [README.md](./README.md)

memoLite is a lightweight memory infrastructure for AI Agent / LLM applications.

It consolidates the common “multi-database, heavy redeploy” memory architecture into a local-first stack:

- **SQLite**: transactional data (`projects/sessions/episodes/semantic`)
- **Kùzu**: Episode/Derivative graph relations and traceability
- **sqlite-vec compatible layer**: vector retrieval (currently SQLite + Python fallback)

> Goal: provide persistent, searchable, and extensible long-term memory for agents while keeping deployment simple.

---

## Features

### 1) Episodic Memory

- Store conversation events (episodes)
- Automatically generate derivative chunks
- Semantic retrieval + filtering (role/type)
- Context window expansion (before/after)

### 2) Semantic Memory

- Manage structured facts via `set/category/tag/feature`
- Vector retrieval + attribute filtering
- Citations (trace facts back to episodes)
- Set-level config and category disabling

### 3) Short-term Memory

- In-session short window cache
- Auto-summary compression when over capacity
- Retrieval response can include short-term context

### 4) Interfaces & Integrations

- **REST API** (FastAPI)
- **MCP Server** (stdio/http)
- **Python SDK** (built-in client)
- **TypeScript client** (`packages/ts-client`)
- **OpenClaw plugin** (`integrations/openclaw`)

### 5) Ops Tooling

- Configure/init: `memolite configure ...`
- Reconcile/repair: `reconcile` / `repair`
- Search benchmark: `benchmark-search`
- API load test: `load-test`

---

## Use Cases

- Local development and single-host agent memory layer
- Lightweight memory service on desktop/edge devices
- Internal knowledge assistants for small and mid-size teams
- AI apps sensitive to deployment complexity and cost

---

## Project Structure

```text
src/memolite/
  app/              # app bootstrap, resource wiring, background recovery
  api/              # REST routes and schemas
  orchestrator/     # unified orchestration layer
  episodic/         # episodic write/search/delete
  semantic/         # semantic service and session manager
  memory/           # short-term and memory-config
  storage/          # SQLite/Kùzu/vector storage implementations
  mcp/              # MCP server
  client/           # Python SDK
  tools/            # benchmark/loadtest/migration
```

---

## Usage

## 1. Installation

### Option A (Recommended): Install from PyPI

```bash
pipx install memolite
# or
pip install memolite
```

If you want local semantic embeddings + reranker support (`sentence-transformers` / `CrossEncoder`):

```bash
pip install 'memolite[embeddings]'
# or, for source development
pip install -e '.[dev,embeddings]'
```

Notes:
- install `memolite` only: good for the hash embedder or setups without a local reranker
- install `memolite[embeddings]`: includes both embedding and reranker dependencies

Best for: regular users, production use, fast setup.

### Option B: Install from source (developers)

- Python `3.12+`
- Run in repository root

```bash
git clone https://github.com/shaun17/memoLite.git
cd memoLite
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Best for: secondary development, debugging, source changes.

Available commands after install:

- `memolite` (unified entry, recommended)
- `memolite-mcp-stdio`
- `memolite-mcp-http`

## 2. Initialize config and local data (optional)

`memolite configure ...` is for out-of-process config/data management, mainly for:

1. `configure`: generate `.env` (runtime config)
2. `init`: initialize local data dir and DB schema (SQLite/Kùzu)
3. `detect-sqlite-vec`: check sqlite-vec extension availability (optional)

```bash
memolite configure configure --output .env --data-dir ~/.memolite
memolite configure init --data-dir ~/.memolite
```

Optional: detect sqlite-vec extension

```bash
memolite configure detect-sqlite-vec --extension-path /path/to/sqlite-vec.dylib
```

## 3. Start service (optional)

```bash
# foreground mode (dev/debug)
MEMOLITE_PORT=18731 memolite serve
```

Default address: `http://127.0.0.1:18731`

> Note: if you use `memolite openclaw setup`, it will automatically install/start the background service, so Steps 2/3 can be skipped.

## 4. Service management and auto-start (recommended)

> Conventions:
>
> - `memolite-server`: foreground run, good for development/debug (lazy init)
> - `memolite service ...`: managed lifecycle commands (install/enable/disable/start/stop/restart/status/uninstall)
> - Auto-start is changed only by `install --enable` / `enable`
> - `start/restart` only affect runtime state and must NOT change auto-start policy
>
> Unified CLI:
>
> ```bash
> # install service definition (no auto-start)
> memolite service install
>
> # enable auto-start and start now
> memolite service enable
>
> # or one step
> memolite service install --enable
>
> # lifecycle
> memolite service start
> memolite service stop
> memolite service restart
> memolite service status
>
> # disable auto-start / uninstall service definition
> memolite service disable
> memolite service uninstall
> ```
>
> Platform details:
>
> - macOS: LaunchAgent (`~/Library/LaunchAgents/ai.memolite.server.plist`)
> - Linux: systemd user service (`~/.config/systemd/user/ai.memolite.server.service`)
>
> If you need user-level services to keep running when logged out (Linux), enable linger:
>
> ```bash
> loginctl enable-linger "$USER"
> ```

## 5. OpenClaw one-shot integration (Plan A script)

```bash
memolite openclaw setup
```

This script will automatically:

1. Run `openclaw plugins install <plugin-path>`
2. Write memolite config into `~/.openclaw/openclaw.json`
3. Install and enable memolite background service (default port 18731)
4. Restart OpenClaw gateway
5. Perform health and plugin load checks

Overridable parameters (CLI):

```bash
memolite openclaw setup \
  --base-url http://127.0.0.1:18731 \
  --org-id openclaw \
  --project-id openclaw \
  --user-id openclaw \
  --auto-capture true \
  --auto-recall true \
  --search-threshold 0.5 \
  --top-k 5
```

Parameter descriptions:

- `--base-url`: memolite service URL, default `http://127.0.0.1:18731`
- `--org-id`: organization identifier (default `openclaw`)
- `--project-id`: project identifier (default `openclaw`)
- `--user-id`: user identifier (default `openclaw`)
- `--auto-capture`: auto store conversation memory (`true/false`)
- `--auto-recall`: auto recall relevant memory (`true/false`)
- `--search-threshold`: retrieval threshold (0~1, higher = stricter)
- `--top-k`: max candidates returned per retrieval

Plugin update (recommended flow):

```bash
# Upgrade package (gets latest bundled plugin)
pipx upgrade memolite

# Reinstall plugin and refresh OpenClaw config
memolite openclaw setup

# Restart gateway so new plugin is loaded
openclaw gateway restart

# Verify plugin name/version
openclaw plugins list | rg "openclaw-memolite|MemoLite"
```

If the plugin version still looks stale, force-clean and reinstall:

```bash
memolite openclaw uninstall
rm -rf ~/.openclaw/extensions/openclaw-memolite
memolite openclaw setup
openclaw gateway restart
```

Additional ops subcommands:

```bash
# status and diagnosis
memolite openclaw status
memolite openclaw doctor

# view / update / reset config
memolite openclaw configure show
memolite openclaw configure set --base-url http://127.0.0.1:18731
memolite openclaw configure reset

# uninstall integration (remove memolite-related parts only)
memolite openclaw uninstall --dry-run
memolite openclaw uninstall
```

## 6. Minimal REST flow

### 6.1 Create project

```bash
curl -X POST http://127.0.0.1:18731/projects \
  -H 'content-type: application/json' \
  -d '{
    "org_id": "demo-org",
    "project_id": "demo-project",
    "description": "quickstart"
  }'
```

### 6.2 Create session

```bash
curl -X POST http://127.0.0.1:18731/sessions \
  -H 'content-type: application/json' \
  -d '{
    "session_key": "demo-session",
    "org_id": "demo-org",
    "project_id": "demo-project",
    "session_id": "demo-session",
    "user_id": "demo-user"
  }'
```

### 6.3 Write memory

```bash
curl -X POST http://127.0.0.1:18731/memories \
  -H 'content-type: application/json' \
  -d '{
    "session_key": "demo-session",
    "semantic_set_id": "demo-session",
    "episodes": [
      {
        "uid": "ep-1",
        "session_key": "demo-session",
        "session_id": "demo-session",
        "producer_id": "demo-user",
        "producer_role": "user",
        "sequence_num": 1,
        "content": "Ramen is my favorite food."
      }
    ]
  }'
```

### 6.4 Search memory

```bash
curl -X POST http://127.0.0.1:18731/memories/search \
  -H 'content-type: application/json' \
  -d '{
    "query": "favorite food",
    "session_key": "demo-session",
    "session_id": "demo-session",
    "semantic_set_id": "demo-session",
    "mode": "mixed"
  }'
```

Important response fields:

- `episodic_matches`
- `semantic_features`
- `combined`
- `expanded_context`
- `short_term_context`

---

## Python SDK Example

```python
import asyncio
from memolite.client import MemLiteClient


async def main() -> None:
    async with MemLiteClient(base_url="http://127.0.0.1:18731") as client:
        await client.projects.create(org_id="demo-org", project_id="demo-project")
        await client.memory.add(
            session_key="demo-session",
            episodes=[
                {
                    "uid": "ep-1",
                    "session_key": "demo-session",
                    "session_id": "demo-session",
                    "producer_id": "demo-user",
                    "producer_role": "user",
                    "sequence_num": 1,
                    "content": "Ramen is my favorite food.",
                }
            ],
        )
        result = await client.memory.search(
            query="favorite food",
            session_key="demo-session",
            session_id="demo-session",
        )
        print(result.combined)


asyncio.run(main())
```

Full example: `examples/python_sdk_quickstart.py`

---

## MCP Usage

### Start

```bash
memolite-mcp-stdio
# or
memolite-mcp-http
```

### Common tools

- `set_context`
- `add_memory`
- `search_memory`
- `delete_memory`
- `list_memory`
- `get_memory`

See: `docs/mcp-guide.md`

---

## Common Ops Commands

```bash
# export/import
memolite configure export --output snapshot.json --data-dir ~/.memolite
memolite configure import --input snapshot.json --data-dir ~/.memolite

# reconcile/repair
memolite configure reconcile --output reconcile.json --data-dir ~/.memolite
memolite configure repair --output repair.json --data-dir ~/.memolite

# search benchmark / load test
memolite configure benchmark-search --output benchmark.json --data-dir ~/.memolite
memolite configure load-test --base-url http://127.0.0.1:18731 --total-requests 200 --concurrency 20
```

---

## Documentation Index

- `docs/quickstart.md`
- `docs/architecture.md`
- `docs/api-reference.md`
- `docs/sdk-usage-guide.md`
- `docs/mcp-guide.md`
- `docs/config-reference.md`
- `docs/deployment-guide.md`
- `docs/troubleshooting.md`
- `docs/faq.md`

---

## Current Status

memoLite already provides a runnable end-to-end prototype (write/search/delete, MCP, SDK, repair tooling).
Before production rollout, you may want to further enhance:

- stronger embedding/provider integrations
- richer semantic extraction strategy
- vector retrieval backend performance
- monitoring and capacity planning
