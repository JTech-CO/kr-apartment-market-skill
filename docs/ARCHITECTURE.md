# Runtime Architecture

## Components

```text
FastMCP
├─ canonical tools
│  ├─ location resolver
│  ├─ unified transaction query
│  ├─ complex analytics
│  ├─ regional analytics
│  ├─ deterministic finance
│  └─ watchlist
├─ PublicDataClient
│  ├─ endpoint registry
│  ├─ retry/backoff
│  ├─ pagination
│  ├─ secure XML parsing
│  └─ normalization
├─ Metrics Service
├─ Local JSON Store
└─ Vendored Compatibility Registration
```

## Trust boundaries

- MCP client input is untrusted.
- API keys are process secrets.
- Public API payload is untrusted XML and parsed with defusedxml.
- Raw records are returned only when explicitly requested.
- Local watchlist is not a multi-user security boundary.
- Apt2Me remains link-only unless authorization metadata changes.

## Scaling path

```text
single process/on-demand
→ shared HTTP client + bounded cache
→ PostgreSQL raw/revision store
→ Redis region-month cache
→ ingestion workers
→ OAuth/RLS watchlists
→ scheduled signal materialization
```
