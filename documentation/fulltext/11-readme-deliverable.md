*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 12. README (required deliverable)

- **What changed** — fetches full bill XML from GovInfo, parses, builds local full-text indexes, rather than proxying API responses.
- **No new API key needed** — the existing congress.gov key works, since both APIs sit behind api.data.gov. Say this explicitly; users will assume otherwise.
- **Where data lives** — resolved cache path per platform.
- **How much disk** — 500MB cap, how to change it, `congressmcp cache clear`.
- **First-call latency** — the measured numbers from step V2, not a guess. Note the client-timeout implication.
- **Offline behavior** — explicitly cached versions queryable offline; `version=None` offline is best-effort and labelled `cached_offline`.
- **Network egress** — `api.congress.gov` (metadata) and `api.govinfo.gov` (content).

---
