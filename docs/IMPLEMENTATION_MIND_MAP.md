# Atlas implementation mind map

This map represents the operational knowledge system, not merely a presentation diagram. Import this Markdown into Xmind, or render the Mermaid map below in compatible Markdown tools.

```mermaid
mindmap
  root((Atlas Intelligence))
    User experience
      Intelligence inbox
        Material changes
        Why it matters
        Coverage status
      Entity dossiers
        Companies and groups
        People and roles
        Capital and ownership
        Public meetings
      Evidence graph
        Nodes stay legally distinct
        Temporal sourced edges
        Event lifecycle
        Historical replay
      Strategy radar
        Possible action and horizon
        Supporting evidence
        Contradictions
        Alternatives
        Next checks
      Investigations
        Important-event trigger
        User question
        Bounded retrieval
        Cited result
    Knowledge model
      Organization
      Business group
      Person
      Trust and fund
      Technology and product
      Facility and geography
      Document claim event
      Hypothesis and review
    Evidence states
      Illustrative
      Reported lead
      User reviewed
      Corroborated
      Primary confirmed
      Disputed or retracted
    Ingestion
      India filings and issuers
      SEC and global regulators
      GDELT and permitted RSS
      Procurement patents trials jobs
      Approved social APIs
      Hash and deduplicate
      Entity resolution
      Event clustering
    AI engine
      Groq adapter
      Schema validated extraction
      Citation allow list
      Materiality ranking
      Competing hypotheses
      Quotas and deferred work
      No private mind reading
    Platform
      React interface
      FastAPI service
      Pilot SQLite
      Production PostgreSQL
      SQS workers and DLQ
      S3 evidence and backups
      Secrets Manager
      CloudWatch
    Trust and safety
      Private authentication
      Tenant and secret isolation
      Prompt injection resistance
      Corrections propagate
      Source rights and retention
      Visible blind spots
    Delivery
      Current vertical slice
        Demo and live separation
        Reviewed evidence entry
        GDELT discovery
        Persistent watchlists
        Investigation dossiers
      Next 20 companies
        Tata structure
        Reliance structure
        India priority sources
      Shadow run
      Quality gates
      Expand to 100
```

## Event-to-insight flow

```mermaid
flowchart LR
    S[Approved source] --> D[Discover and deduplicate]
    D --> R[Resolve legal entities]
    R --> C[Extract claims]
    C --> V{Evidence state}
    V -->|Lead only| Q[Review queue]
    V -->|Supported| E[Temporal event graph]
    Q --> E
    E --> M[Materiality ranking]
    M --> I[Bounded investigation]
    I --> H[Strategy hypotheses]
    H --> A[Inbox and dossier]
    A --> F[User review and correction]
    F --> E
```

## Frontend navigation

```mermaid
flowchart TD
    O[Overview] --> F[Intelligence feed]
    O --> G[Compact graph]
    O --> S[Strategy preview]
    F --> E[Event dossier and evidence]
    G --> N[Entity or relationship dossier]
    S --> H[Hypothesis ledger]
    C[Companies] --> N
    W[Watchlist] --> N
    I[Investigations] --> J[Cited research dossier]
    X[Sources and coverage] --> K[Connector health and manual sync]
    N --> J
    E --> J
```
