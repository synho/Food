# Health Navigation Web

Next.js 14 (App Router) client for the Health Navigation API. Standardized UI: **blue** (Information), **green** (Knowledge), **gold** (Wisdom) trust badges per project rules.

## Setup

```bash
cd web
npm install
```

## Run

Start the API first (from repo root: `uvicorn server.main:app --reload`). Then:

```bash
npm run dev
```

Open http://localhost:3000. If that port is already in use, run `npm run dev:3001` and open http://localhost:3001 instead. The app rewrites `/api-backend/*` to `http://127.0.0.1:8000/*` so API calls hit the server.

## Features

- **Input flow**: Age, conditions, symptoms, goals (optional; comma-separated).
- **Output**: Recommended foods, restricted foods, position & nearby risks, safest path, early-signal guidance, general guidance—all with evidence.
- **Evidence display**: Each recommendation/restriction shows source (journal, date) and context; trust badges by type (Information / Knowledge / Wisdom).

## Env

Optional: `NEXT_PUBLIC_API_URL` for server URL when not using the default rewrite (e.g. in production).
