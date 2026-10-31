# Atlas implementation mind map

This map represents the operational knowledge system, not merely a presentation diagram. Import this Markdown into Xmind, or render the Mermaid map below in compatible Markdown tools.

This is the full product blueprint, including planned connectors and models. For the implemented data flow, current capabilities and remaining limits, see [IMPLEMENTED_UPGRADE.md](IMPLEMENTED_UPGRADE.md).

The [V2 strategy and business-gap plan](STRATEGY_INTELLIGENCE_V2_PLAN.md) adds the business-unit/capability/portfolio knowledge map and an implementation DAG for strategic and opportunity analysis.

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
      OpenAlex Crossref grants and spending
      Mastodon Bluesky and permitted feeds
      Optional metered X API
      Approved LinkedIn products only
      RSSHub route-by-route evaluation
      Hash and deduplicate
      Entity resolution
      Event clustering
    AI engine
      LangGraph investigation DAG
        Intent router
        Hybrid retrieval node
        Evidence sufficiency gate
        Groq synthesis node
        Schema validation node
        Citation audit node
        Persisted workflow trace
      Micro retrieval domains
        Capital and deals
        People and leadership
        Technology
        Geography and regulation
        Risk
        Strategy
      Retrieval fusion
        Lexical relevance
        Temporal recency
        Evidence tier prior
        Two hop graph expansion
        MMR style diversity
        Token budget packing
      Trust controls
        Citation allow list
        Competing explanations
        Missing evidence
        Evidence only fallback
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
      S3 run manifests and local metrics
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
    M --> I[LangGraph routed investigation]
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
