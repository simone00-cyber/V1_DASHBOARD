# Hormuz Maritime Intelligence

The active Maritime Intelligence page uses the public Hormuz Strait Monitor dashboard feed:

- `https://hormuzstraitmonitor.com/api/dashboard`
- 10-minute Streamlit cache
- retry/backoff HTTP client
- schema validation
- offline JSON snapshot upload
- downloadable raw snapshot and provenance audit

AISStream remains in the repository only as legacy/experimental code and is not imported by the active page.

## Dashboard modules

- Overview: strait status, transits, DWT throughput, vessel queue, Brent, insurance and VLCC rates
- Risk & Diplomacy: war-risk premium and negotiation monitor
- Global Trade: oil/LNG exposure, regional dependency and supply-chain impact
- Alternative Routes: extra days and costs
- Crisis Timeline: event-type filters
- News: source-linked headlines
- Data Audit: timestamps, endpoint and raw payload
