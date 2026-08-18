# Known-failing baseline

**Why this file exists.** The suite does not run clean, and until now the set of
failures was carried in people's heads. An unenumerated known-failure baseline is the
A3 shape: a real regression eventually hides among failures everyone has learned to
scroll past, and nothing announces the moment it does. Enumerating the set converts
"6 failures, same as before" from a memory into a check.

Run `python tests/check_known_failures.py` to verify the live set still equals the set
recorded here. It fails if the set **grows** (a regression) or **shrinks** (something
was fixed and this file was not updated). Neither direction is silent.

**The fenced code blocks below ARE the baseline.** `check_known_failures.py` parses
them directly -- an entry with a `::` node id is a known test failure, a bare path is a
known collection error. There is deliberately no second copy of the set anywhere: two
unlinked records of a baseline desync (F24 sub-finding #20). Edit the fences, and the
check follows.

**None of these involve `congress_api/features/bill_text/`.** They pre-date the
bill-text branch; verified by running the same suite on the base commit.

**Removed 2026-08-14 (F24):** the six `test_*_hub_bucket.py` files that failed
collection on the undeclared standalone `fastmcp` package were deleted, not fixed.
They tested the removed tier-era architecture (`congress_api.core.auth.auth`,
`FREE_OPERATIONS`/`PAID_OPERATIONS`, bucket modules since renamed or replaced), so no
import fix could make them collect. The territory they claimed -- operation routing
and parameter validation in the bucket tools -- is now covered by
`tests/test_bucket_operation_guard.py`, which collects and sweeps every live router
branch's `validate_operation_kwargs` raise path.

## Collection errors (4 files, 0 tests run)

### Stale import: `congress_api.core.services` (4 files)

```
tests/test_email_service.py
tests/test_email_templates.py
tests/test_upgrade_email.py
tests/test_user_creation.py
```

`ModuleNotFoundError: No module named 'congress_api.core.services'`. The module does
not exist anywhere in the tree, so these test a package layout that is gone.

## Test failures (2)


### Async tests with no async plugin (2)

```
tests/test_registration_endpoint.py::test_registration_endpoint
tests/test_registration_endpoint.py::test_health_endpoint
```

`Failed: async def functions are not natively supported`. `pytest-asyncio` is
installed (the bill-text async tests use `@pytest.mark.asyncio`) but no `asyncio_mode`
is configured and these two functions carry no marker.
