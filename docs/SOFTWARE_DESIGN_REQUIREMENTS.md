# Atlas Intelligence — Software Design Requirements

Version 0.1 · 27 October 2026 · Status: implemented pilot and next-stage specification

## 1. Product definition

Atlas is a private research desk that answers four questions:

1. What materially changed around a company or business group?
2. Which people, organizations, capital flows, technologies, and prior events connect to it?
3. What possible strategic moves does the public evidence support or weaken?
4. What evidence is missing, contradictory, stale, or inaccessible?

The graph is the product memory. The frontend is a set of evidence-linked views over that memory. “Everything” means everything collected from explicitly monitored sources, with visible coverage gaps; it never means guaranteed access to every public or private event.

Primary user: one private research-desk owner. Initial depth: 100 monitored companies, weighted toward India, with wider discovery. Tata and Reliance group structures are mandatory priorities. The graph may include unlimited related people, funds, trusts, counterparties, technologies, and events without consuming monitored-company slots.

### Success criteria

- A material development can be understood, sourced, connected, and investigated from one workspace.
- Every displayed factual relationship has an evidence record and date.
- Demo scenarios, reporting leads, user-reviewed claims, accepted facts, and AI hypotheses remain visibly distinct.
- A researcher can add a sourced relationship without editing code.
- An AI result cannot cite evidence outside the retrieved allow-list.
- Coverage failures and provider quotas appear as product state, never as silence or inferred inactivity.

## 2. Frontend information architecture

### Overview

The landing view shows registry size, current evidence volume, hypotheses, investigation usage, a ranked intelligence feed, a compact graph, and the strategy-radar entry point. Dataset controls switch between synthetic demonstration scenarios and collected reporting.

### Intelligence graph

Displays company, person, group, trust, technology, and event connections. Users can zoom, pan, select nodes, inspect edges, and open evidence. A reviewed-evidence form creates a dated relationship between two existing real registry entities. Headline discovery never creates an edge automatically.

### Companies and watchlist

Searchable registry with group, sector, country, qualification state, and persistent watchlist control. The entity drawer shows connected developments and explicit data gaps. India group membership is presented without collapsing separate legal entities.

### Strategy radar

Shows up to three active hypotheses per deeply monitored company. Each requires a specific possible action and horizon, supporting evidence, contradictory evidence, alternatives, next checks, and one of: insufficient, emerging, supported, weakened, or resolved. The pilot’s preloaded hypotheses are synthetic examples only.

### Investigations

Creates a bounded job for one entity and research question. It retrieves same-dataset evidence, optionally asks Groq for source-grounded synthesis, validates citations, persists the dossier, and exposes deferred/failed states. Without Groq, the user receives an evidence inventory rather than simulated AI output.

### Sources and coverage

Shows access method, connector readiness, last attempt, last success, inserted records, and errors. It supports manual GDELT headline discovery. Cards for Indian filings, SEC EDGAR, and social sources remain marked planned/unavailable until actual access is implemented.

## 3. Domain and evidence model

Core entities: Organization, BusinessGroup, Person, Trust, Fund, Technology, Product, Facility, Geography, Document, Claim, Event, Hypothesis, Investigation, SourceRun, and Review.

Core relationships: controls, owns_stake_in, subsidiary_of, member_of_group, serves_as, advises, invests_in, participates_in_round, supplies, partners_with, competes_with, develops, operates, announced, attended, met_with, discussed, supports, and contradicts.

An edge must contain source entity, target entity, controlled relation type, evidence ID, observed time, effective time when available, review status, and dataset marker. Ownership additionally requires percentage, share/voting basis, and as-of date when disclosed. Unknown values remain unknown.

Events are reified nodes: participants attach with roles, and the event attaches to claims and evidence. This supports rumor → announcement → approval → completion/cancellation without overwriting history.

Evidence states:

| State | Meaning | May create graph edge automatically? |
|---|---|---|
| Illustrative | Synthetic UI/workflow example | Only in demo dataset |
| Reported | Headline or report lead | No |
| User-reviewed | User says the cited source supports the precise statement | Yes, labelled user-reviewed |
| Corroborated | Independent source lineages agree | After verification pipeline exists |
| Primary-confirmed | Official disclosure directly supports claim | After source-specific validation |
| Retracted/disputed | Evidence was withdrawn or credibly contradicted | Invalidates dependent summaries |

Maintain valid time and knowledge time. Historical queries must exclude evidence learned later. Never infer a private meeting from shared attendance, proximity, or travel, and never assign one group company’s action to its chair, parent, or sibling without evidence.

## 4. Processing, AI, and source requirements

Pipeline: discover → normalize → hash/deduplicate → resolve entities → extract claims → verify → store evidence and temporal edges → rank materiality → investigate → render alerts and dossiers.

The pilot includes manual collection and reviewed evidence. The production pipeline adds scheduled workers, source-specific parsers, entity-review queues, event clustering, correction propagation, and alert outbox delivery.

### Groq adapter

- The API key exists only on the server.
- Model ID is configuration, because provider availability changes.
- Input consists of an entity, question, dataset label, and bounded evidence array.
- Collected documents are untrusted data and cannot issue tool instructions.
- Output must validate to `{ result: string, citations: string[] }`.
- Every citation must reference an ID in the supplied evidence array; empty or invented citation arrays fail closed.
- HTTP 429 becomes deferred, preserving evidence. Provider errors never become conclusions.
- Daily investigations are capped; 25% of future scheduled inference capacity remains reserved for user questions.

### Free-first sources

First sources: issuer disclosures, exchange/regulator filings, company investor relations, permitted RSS, GDELT discovery, public professional biographies, government procurement, patents, clinical trials, open scholarly data, open social networks, and accessible job boards. A public webpage is not automatically a permitted API. Each connector needs a source owner, access method, collection/retention rights, rate policy, health state, and deletion policy. The detailed order and connector controls are in [the free and open-source ingestion plan](OPEN_SOURCE_INGESTION_PLAN.md).

X is an optional metered connector under its current pay-per-use model. LinkedIn monitoring remains restricted to data allowed by an approved product and granted OAuth scopes; its open permissions do not provide arbitrary company-feed reads. Open-source adapters may be evaluated per route, but they do not replace upstream permission or make coverage complete. Groq access does not supply news or social data.

### Materiality and hypotheses

Materiality combines watchlist priority, event type, novelty, directness, evidence strength, and affected graph paths. Article volume alone cannot cause high priority. Automatic traversal is capped at two hops and 100 neighbors.

Hypotheses describe public-evidence possibilities, never hidden chain-of-thought or private mental state. Numerical likelihoods are prohibited until historical calibration demonstrates reliability.

## 5. Interfaces and operations

Implemented API surface:

- `GET /api/health` — readiness and authentication requirement.
- `POST /api/session` — exchanges workspace token for an HttpOnly, SameSite cookie.
- `GET /api/workspace` — normalized workspace snapshot.
- `GET /api/entities/{id}` — entity registry record.
- `PUT /api/watchlist/{id}` — persistent watch state.
- `POST /api/evidence` — idempotent reviewed relationship with source and date.
- `POST /api/investigations` and `GET /api/investigations/{id}` — bounded async dossier workflow.
- `POST /api/sources/gdelt/sync` — rate-limited, fixed-host metadata discovery for a registry entity.

Current persistence is SQLite/WAL for one process and one user. Jobs running during a restart become interrupted instead of remaining falsely active. Standard API mutations reject foreign browser origins. Remote deployment requires HTTPS, a 24+ character workspace token, HttpOnly secure cookies, private database/storage access, secret management, and audit logs.

Production evolution:

- PostgreSQL when more than one worker/user writes concurrently, the evidence corpus exceeds practical SQLite operation, or historical graph queries need indexed temporal joins.
- SQS plus a dead-letter queue when scheduled ingestion begins; all consumers remain idempotent because delivery can repeat.
- S3 for permitted raw evidence and encrypted backups.
- Secrets Manager for Groq and source credentials.
- DynamoDB control records, SQS/DLQ inspection, local rotated container logs, the health API, and private S3 run manifests for queue state, connector health, analysis backlog, model usage, latency, errors, and spend.

No Neptune, OpenSearch, Kubernetes, or Bedrock is required for the first 100 companies.

## 6. Reliability, security, and acceptance

Functional acceptance:

- 100% of displayed material claims open traceable evidence.
- Demo and collected datasets never merge in feed, graph, hypotheses, or investigation retrieval.
- Duplicate source URLs and duplicate reviewed-evidence submissions do not create duplicate records.
- Watchlist and investigations survive restart.
- Source failure is visible and never reported as successful or as company inactivity.
- Invalid entity IDs, unsafe source URL schemes, invalid dates, unreviewed evidence, and self-edges fail validation.

Quality targets for the next data pipeline: at least 99% precision for auto-accepted entity merges, 95% accuracy for headline event amount/currency on a held-out set, 90% analyst relevance for high-priority alerts, and under 2% duplicate alerts. Report denominators and results by language/source class.

Required tests include: similar names; group versus subsidiary; personal versus corporate investment; crore conversion; announcement versus closing; meeting scheduled/cancelled; co-attendance without a meeting; syndicated sources; retraction; contradictions; 429 handling; retry duplicates; prompt injection; invalid model citations; later evidence excluded from historical queries; authentication and cross-origin mutations; source outage; and insufficient evidence.

Rollout gates:

1. Pilot with 20 companies including Tata and Reliance entities; confirm source access and graph precision.
2. Two-week shadow run with no automatic high-priority alerts.
3. Expand to 100 companies only after accuracy, duplicate, cost, and coverage-health targets pass.
4. Add languages and premium/social sources one at a time with an access and evaluation record.
