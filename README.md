# Atlas Intelligence

Atlas is a private, evidence-first company intelligence workspace. It connects companies, people, capital, technologies, events, and strategic hypotheses while keeping illustrative examples separate from collected reporting.

## What works in this pilot

- Responsive intelligence inbox, company registry, watchlist, strategy radar, investigations, graph, and source-health views.
- Persistent SQLite storage for entities, events, reviewed relationships, watchlists, source runs, usage, and investigation dossiers.
- Interactive evidence graph: every visible edge opens its supporting event and evidence.
- Manual reviewed-evidence entry for constructing real relationships with a URL, publisher, date, and precise statement.
- GDELT metadata discovery for a selected company. It stores headlines and publisher links as unverified reporting leads; it does not scrape article bodies.
- Conditional LangGraph investigations with intent routing, lexical/temporal/graph retrieval, MMR-style diversity, context budgets, sufficiency gates, Groq synthesis, citation auditing, and evidence-only fallback.
- Durable AWS mode with separate SQS ingestion and analysis workers, dead-letter queues, DynamoDB checkpoints, S3 run manifests, and a disabled-by-default EventBridge schedule.
- Deterministic evidence classes and source-routing tiers attached before model synthesis.
- Private access-token gate for network deployment.
- Explicit demo/live separation. Demo events and hypotheses are synthetic and labelled throughout the interface.
- Offline migration of a 1,372-company sourced candidate catalog with 100 memberships per broad discovery portfolio; sector/country filters, pagination, provenance and coverage gaps.
- Freshness-aware live investigations, optional historical cutoff, authenticated live UI updates, and saving cited analyses as draft strategy hypotheses.
- Optional isolated Python 3.13 CrewAI analysis worker with capital, sector and skeptic tasks; standard analysis remains on Python 3.14.
- Official SEC submissions/annual-profit facts and five NSE disclosure feeds, with reviewed issuer mappings and source-specific collection status.
- Sourced financial qualification above USD 500M, public-profile entry, configurable monitoring rules, and deduplicated in-app materiality alerts.
- Versioned corrections that flag relationships and hypotheses, withdraw alerts and update qualification; interrupted LangGraph investigations resume from durable SQLite checkpoints.

This release does **not** claim complete news coverage, prove user-entered evidence, or infer private thoughts. Planned source cards are honest placeholders rather than simulated integrations. Scheduled collection starts only after its Terraform switch is enabled.

## Run locally

Requirements: Node 20+, Python 3.14+, npm.

```bash
cd /Users/apple/Downloads/strategy-mapping
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm ci
npm run build
export AWS_PROFILE=account2 AWS_REGION=us-east-1
export ATLAS_RUNTIME_SECRET_ID=/atlas/production/runtime
./scripts/start.sh
```

Open `http://127.0.0.1:8000`. Keep `.env` for non-secret settings. The startup process loads `GROQ_API_KEY`, `ATLAS_ACCESS_TOKEN` and optional `SEC_USER_AGENT` directly from AWS Secrets Manager using your selected AWS profile. Do not copy their values into source files. Without a configured secret or model credential, investigations return an evidence inventory.

For private network access, set `ATLAS_HOST=0.0.0.0` and store a random `ATLAS_ACCESS_TOKEN` of at least 24 characters in the runtime secret. Terminate HTTPS at a reverse proxy and set `ATLAS_SECURE_COOKIE=true`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The default port mapping binds only to loopback. Put the service behind authenticated HTTPS before making it remotely reachable.
Set the non-secret runtime secret identifier and region in `.env`; the container also needs AWS IAM credentials (the EC2 instance role in AWS). The local Compose file does not automatically mount your host AWS profile.

## Verification

```bash
.venv/bin/python -m pytest -q
npm run build
npm run test:e2e
```

The API suite covers persistence, authentication, quotas, evidence validation, prompt/citation safety, retry states, deduplication, and demo/live isolation. Browser tests cover the core desktop and mobile workflows.

## Documents

- [Implemented upgrade and CrewAI deployment options](docs/IMPLEMENTED_UPGRADE.md)
- [Product audit and complete upgrade plan](docs/PRODUCT_UPGRADE_PLAN.md)
- [Software design requirements](docs/SOFTWARE_DESIGN_REQUIREMENTS.md)
- [Implementation mind map](docs/IMPLEMENTATION_MIND_MAP.md)
- [Free and open-source ingestion plan](docs/OPEN_SOURCE_INGESTION_PLAN.md)
- [Architecture upgrade and production topology](docs/ARCHITECTURE_UPGRADE.md)
- [LangGraph and hybrid RAG architecture](docs/LANGGRAPH_RAG_ARCHITECTURE.md)
- [AWS deployment plan](docs/AWS_IMPLEMENTATION.md)

## Current architecture

```text
React client ── FastAPI ── SQLite evidence graph
                    ├──── SQS ingestion ── ingestion worker ── approved sources
                    ├──── SQS analysis ─── LangGraph worker ── routed hybrid RAG ── Groq
                    └──── DynamoDB checkpoints + private S3 manifests/backups
```

SQLite is deliberate while all writers share one host. The SDR defines the measured threshold for PostgreSQL and horizontally scaled workers.
