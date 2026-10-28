# Implemented registry and live-research upgrade

Delivered 29 October 2026. This document describes executing code and its limits.

## Registry

`server/data/company_registry.json` contains 1,372 distinct Wikidata candidates and 100 memberships in each of 15 broad discovery portfolios. The original local companies and Indian group entries remain. A company can belong to multiple portfolios. Portfolio membership does not establish niche capability: Quantum & Advanced Compute includes semiconductor companies; Spatial & Space Intelligence includes space-industry companies; Aerospace & Defence does not certify defence-AI activity.

The snapshot is CC0 source data with per-company Wikidata links, source revision when available, aliases and a generation timestamp. It is an identity/discovery catalog, not a financial eligibility list. Current operating status, country attribution, ownership and the USD 500M threshold still require primary verification.

The startup migration runs offline, hashes the snapshot, preserves existing local IDs/notes/watchlists, and avoids overwriting user-maintained fields. Existing SQLite databases expand after restart. Startup never queries Wikidata. To regenerate the snapshot intentionally:

```bash
.venv/bin/python scripts/build_company_registry.py
```

The builder uses an ignored resumable fetch cache, bounded requests, a company-type filter and source-error reporting. Inspect the catalog diff before committing a new snapshot.

Frontend: Companies now has sector and country filters, 50-row pages, provenance links and portfolio coverage/gaps. Server API supports `GET /api/companies?q=&sector=&country=&offset=0&limit=50` and `GET /api/registry/coverage`.

## Latest reporting and historical research

New live investigations default to `refresh_sources=true`. LangGraph checks the selected company's collection age before retrieval. A fresh collection uses the cache; stale or unknown collection invokes the fixed-host news adapter. A shared SQLite cooldown coordinates API and workers. A source outage or cooldown is retained in `acquisition`; the answer can use stored evidence and the dossier shows the achieved freshness.

The freshness timestamp means a successful collection check of the connected source, not complete coverage or guaranteed real-time publication. GDELT remains the only automated news connector in this delivery. Demo investigations do not request live data.

An optional `as_of` timestamp filters both publication/effective time and observation time before retrieval and graph expansion. It disables refresh for the historical question. This prevents newly learned records from leaking into a historical answer, but is not a full bitemporal correction store; versioned corrections remain future work.

API example:

```json
{
  "entity_id": "jio",
  "question": "What changed and which evidence supports a possible strategic shift?",
  "demo": false,
  "refresh_sources": true,
  "analysis_mode": "standard",
  "as_of": null
}
```

## Optional real CrewAI team

`server/intelligence/crew.py` executes three sequential CrewAI tasks: capital analyst, sector analyst, and skeptical editor. Each receives the bounded raw evidence packet and structured predecessor outputs. It uses Pydantic reports, citation allowlists, no tools, no recursive delegation, one agent iteration, zero guardrail retries, provider timeouts and per-agent execution limits. Memory, caching, verbose output and tracing are disabled. LangGraph performs final validation after the team returns.

CrewAI is pinned to the tested 1.9.3 release. The newest release requires an unavailable LanceDB dependency on this Intel Mac; CrewAI also requires Python below 3.14. The ordinary Atlas image stays on Python 3.14. `Dockerfile.crew` uses Python 3.13 and a separate tested dependency lockfile. Real-framework tests use a deterministic model: three tasks produced three calls, and an invented citation was rejected. These tests do not measure live Groq response quality.

Enable for AWS deployment by setting Terraform `crew_worker_enabled=true`, reviewing/applying the plan, and running the deployment document. It builds the optional worker image, uses it for the analysis queue and exposes the CrewAI selector in the API/UI. Secrets continue to load from Secrets Manager through the instance role. No infrastructure was applied during development.

For a local Python 3.13 process with CrewAI:

```bash
python3.13 -m venv .venv-crew
.venv-crew/bin/pip install -r requirements-crew.lock
AWS_PROFILE=account2 AWS_REGION=us-east-1 \
ATLAS_RUNTIME_SECRET_ID=/atlas/production/runtime \
ATLAS_CREW_ENABLED=true OTEL_SDK_DISABLED=true \
CREWAI_TELEMETRY_DISABLED=true CREWAI_TRACING_ENABLED=false \
.venv-crew/bin/python -m server.start
```

The standard Python 3.14 startup command continues to work, with standard analysis. Do not enable CrewAI in a process lacking the optional dependencies or route crew jobs to the standard analysis image.

## Live UI and strategy radar

SQLite transactions append small change records through triggers. Authenticated `GET /api/updates` streams invalidation events with monotonically increasing cursor IDs. The browser reconnects with `Last-Event-ID`, refreshes on change and retains a 15-second polling fallback. This streams committed application changes; it does not create an upstream news subscription. A browser test verifies an external watchlist mutation appears within eight seconds without reloading.

A completed cited AI investigation can be saved as a **Draft** in Strategy radar. The action is idempotent and carries its citations, alternatives, missing evidence and original investigation ID. Evidence-only inventories cannot be promoted into strategy claims.

## Reliability and operations

- Source failures and deferred analyses reach SQS retry/redrive rather than being acknowledged as success.
- Worker source requests wait through the shared cooldown with bounded retries; long jobs renew their SQS visibility lease.
- Completed analysis deliveries skip repeated inference.
- Provider failures retain retrieval evidence and stage traces.
- API startup preserves jobs owned by durable workers.
- The deployment document fixes ownership of the mounted database directory for non-root containers.
- No CloudWatch or Bedrock service is added.

## Remaining roadmap

Primary India/SEC adapters, verified $500M qualification, normalized temporal claims and correction propagation, true graph checkpoint resume, semantic retrieval evaluation, priority-specific monitoring rules, notifications and PostgreSQL migration remain tracked in `PRODUCT_UPGRADE_PLAN.md`. The catalog and extra agents do not make those capabilities complete. Container builds still require validation on a running Docker daemon or CI.
