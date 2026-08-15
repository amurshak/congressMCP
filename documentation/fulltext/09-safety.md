*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 11. Network and parsing safety

- **XML:** parse with external entity resolution **disabled** and **no network access** for DTD fetching (`resolve_entities=False`, `no_network=True`, or `defusedxml` if already available). Bill DTD documents reference an external DTD; never fetch it.
- **Downloads:** stream with a maximum accepted size for both compressed and decompressed bytes. Abort and error past the ceiling rather than buffering unbounded.
- **HTTP:** explicit connect, read, and total timeouts. Bounded retries with jitter.
- **Secrets:** never in persisted URLs, logs, error payloads, or `govinfo_url`. **Pass the key as an `X-Api-Key` header, not a query parameter.** api.data.gov accepts the header form for both services. Query params end up in httpx's INFO-level URL logging — confirmed leaking the key to stderr during a live run. Fixing this at the source is correct; relying on production log level is not. The congress.gov client has the same defect pre-existing — raise it separately rather than silently widening this PR's scope.
- **Entity expansion:** stdlib expat does not fetch external DTDs or expand external entities by default, so XXE risk is low, but **billion-laughs is unguarded**. Given the no-new-dependencies constraint, **reject any document whose raw bytes contain `<!ENTITY` before parsing.** Bill XML has no legitimate internal entity declarations; this costs nothing and needs no library.

---

---

## Process side effects — a third channel nothing else covers

**The coverage map has three channels, and only two are tested:**

| Channel | Covered by | What it sees |
|---|---|---|
| Response content | V1–V21 | what the parser and index produce |
| Consumer behavior | §17 | what a model does with a correct response |
| **Process side effects** | **nothing** | logs, tracebacks, files written, URLs emitted |

F15 landed on the third: a credential in an INFO log is invisible to every V-step and every prompt in §17. **It took grepping real process output to find**, and it was green in four unit tests at the time. A defect on this channel can be arbitrarily severe while every existing check passes.

**Redaction is installed as a process-global `LogRecord` factory** — chaining to the previous factory, never raising, idempotent, each property pinned by a test that fails when that property alone is removed. A logger filter sees only records made through that logger; a handler filter only handlers attached at install time. The property wanted is *no log record carries the key*, and only a factory delivers it across loggers configured later.

**Non-string arguments must be stringified before testing.** httpx logs `'HTTP Request: %s %s "%s %d %s"'` with an `httpx.URL` object, not a `str`; an `isinstance(value, str)` guard skips exactly the argument carrying the credential and `%s` restores it at emit time.

### Both residuals were real — closed 2026-08-06

**Error envelopes, the worse channel.** `_unexpected` interpolated the exception into `message` and `raise_for_status` embedded the key-bearing URL. **Redaction now happens at the single `_error` construction point**, so every error path is covered rather than the ones known to interpolate an exception today. Chokepoint over enumeration — the right shape, because the enumeration is what went stale in `client_handler.py`.

**Tracebacks.** These bypass `msg` and `args` entirely. `exc_text` alone was **not sufficient**: this server logs through **rich**, and `rich_tracebacks` renders `exc_info` directly, ignoring `exc_text` (measured). A stdlib-only test would have passed while the deployment leaked. Exception `args` are redacted too, which neutralises the message for any renderer that stringifies it.

**Reachability confirmed at `client_handler.py:184` — five lines after code that carefully redacts params for its debug log.** The author guarded the channel they had in mind. This is the *scoping* pattern from `00-INDEX.md`, appearing in security code rather than the parser.

**Stated limit, and it is the honest frame.** A renderer that shows **locals** can still reach `exc.request.url`; nothing here touches that. **All of this is downstream of the key being a query parameter** — these mitigations shrink the surface, they do not close it. The durable fix is the separate PR that moves the congress.gov client to a header, and this should not be mistaken for it.

### The residuals as originally stated, retained for the record

**Uncaught exception tracebacks do not pass through the logging system**, so the factory never sees them. Two paths worth confirming:

1. **Tracebacks printed by the interpreter.** An httpx exception's repr carries the request URL. If the key is a query parameter on the congress.gov client — which §11 leaves pre-existing and out of scope — a crash prints it.
2. **Error envelopes returned to the consumer.** If any error path echoes the request URL into a `detail` or `message` field, **the credential reaches the caller**, which is strictly worse than a log line. `section_not_found` and `ambiguous_section_id` are clean; the network-error paths are the ones to check.

Neither is covered by the factory, and neither is covered by any V-step or §17 prompt.
