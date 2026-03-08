# memoLite (English)

memoLite is a lightweight memory infrastructure for AI agents and LLM applications.

It provides a local-first long-term memory stack with:

- **SQLite** for transactional data (`projects/sessions/episodes/semantic`)
- **Kùzu** for graph relationships and traceability (`Episode/Derivative`)
- **sqlite-vec compatible layer** for vector retrieval (currently SQLite + Python fallback)

> Goal: provide persistent, searchable, and extensible long-term memory for agents while keeping deployment simple.

---

## Key Features

### 1) Episodic Memory

- Store conversation events (episodes)
- Generate derivative chunks automatically
- Semantic retrieval with role/type filters
- Context window expansion for adjacent messages

### 2) Semantic Memory

- Manage structured facts with `set/category/tag/feature`
- Vector retrieval with metadata filters
- Citation support (trace facts back to episodes)
- Set-level config and category disabling

### 3) Short-term Memory

- In-session short window cache
- Auto summarization when history grows
- Attach short-term context in retrieval responses

### 4) Interfaces & Integrations

- **REST API** (FastAPI)
- **MCP Server** (stdio/http)
- **Python SDK** (built-in client)
- **OpenClaw plugin** (`integrations/openclaw`)

### 5) Ops & Tooling

- Config/init: `memolite configure ...`
- Reconcile/repair: `reconcile` / `repair`
- Retrieval benchmark: `benchmark-search`
- API load test: `load-test`

---

## Quick Commands

- `memolite serve` — run API server in foreground
- `memolite service ...` — managed service lifecycle (macOS LaunchAgent / Linux systemd)
- `memolite openclaw setup` — one-shot OpenClaw integration setup
- `memolite openclaw status|doctor|configure|uninstall` — integration operations

---

## Installation

### Option A (Recommended): PyPI

```bash
pipx install memolite
# or
pip install memolite
```

### Option B: Source (for development)

```bash
git clone https://github.com/shaun17/MemoLite.git
cd MemoLite
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

After installation, available commands include:

- `memolite`
- `memolite-mcp-stdio`
- `memolite-mcp-http`
