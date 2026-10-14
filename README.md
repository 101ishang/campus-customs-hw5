# Campus Customs

Campus Customs is a small agentic shop desk. The working database is `data/campus_customs_new.db`; the untouched baseline is `data/campus_customs.db`.

## Clean run

When a fresh run is needed, copy the original database over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Run the reset route before resolving all three tickets through the board:

```bash
curl -X POST http://localhost:8000/api/reset
```

## Start the shop

Export `PORTKEY_API_KEY` from your shell (use `.env.example` as a template), then start the read-only MCP server:

```bash
python mcp_server/server.py
```

In another terminal, start the FastAPI backend:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

In a third terminal, start the React board:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The backend landing page and interactive API docs are at `http://localhost:8000` and `http://localhost:8000/docs`.

Agents use MCP for shop facts, keep customer and vendor communications as drafts, and require a named human approval before outgoing cash is released.
