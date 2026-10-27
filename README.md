# Atlas Intelligence

Atlas is a private, evidence-first company intelligence workspace. It connects companies, people, capital, technologies, events, and strategic hypotheses while keeping illustrative examples separate from collected reporting.

## What works in this pilot

- Responsive intelligence inbox, company registry, watchlist, strategy radar, investigations, graph, and source-health views.
- Persistent SQLite storage for entities, events, reviewed relationships, watchlists, source runs, usage, and investigation dossiers.
- Interactive evidence graph: every visible edge opens its supporting event and evidence.
- Manual reviewed-evidence entry for constructing real relationships with a URL, publisher, date, and precise statement.
- GDELT metadata discovery for a selected company. It stores headlines and publisher links as unverified reporting leads; it does not scrape article bodies.
- Groq-compatible server-side synthesis with citation allow-listing, evidence-only fallback, rate-limit handling, and daily caps.
- Private access-token gate for network deployment.
- Explicit demo/live separation. Demo events and hypotheses are synthetic and labelled throughout the interface.

This release does **not** claim complete news coverage, run background collection, prove user-entered evidence, or infer private thoughts. Planned source cards are honest placeholders rather than simulated integrations.

## Run locally

Requirements: Node 20+, Python 3.14+, npm.

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm ci
npm run build
./scripts/start.sh
```

Open `http://127.0.0.1:8000`. Add `GROQ_API_KEY` to `.env` to enable AI synthesis. Without it, investigations return an honest evidence inventory.

For private network access, set `ATLAS_HOST=0.0.0.0` and a random `ATLAS_ACCESS_TOKEN` of at least 24 characters. Terminate HTTPS at a reverse proxy and set `ATLAS_SECURE_COOKIE=true`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The default port mapping binds only to loopback. Put the service behind authenticated HTTPS before making it remotely reachable.

## Verification

```bash
.venv/bin/python -m pytest tests/test_api.py -q
npm run build
npm run test:e2e
```

The API suite covers persistence, authentication, quotas, evidence validation, prompt/citation safety, retry states, deduplication, and demo/live isolation. Browser tests cover the core desktop and mobile workflows.

## Documents

- [Software design requirements](docs/SOFTWARE_DESIGN_REQUIREMENTS.md)
- [Implementation mind map](docs/IMPLEMENTATION_MIND_MAP.md)
- [Free and open-source ingestion plan](docs/OPEN_SOURCE_INGESTION_PLAN.md)
- [AWS deployment plan](docs/AWS_IMPLEMENTATION.md)

## Current architecture

```text
React client ── FastAPI ── SQLite evidence graph
                         ├─ GDELT metadata connector
                         └─ Groq synthesis adapter
```

SQLite is deliberate for a single-user pilot. The SDR defines the threshold and migration path to PostgreSQL, SQS, S3, and scheduled workers after the research workflow proves useful.
