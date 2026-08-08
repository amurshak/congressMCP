# Known-failing baseline

**Why this file exists.** The suite does not run clean, and until now the set of
failures was carried in people's heads. An unenumerated known-failure baseline is the
A3 shape: a real regression eventually hides among failures everyone has learned to
scroll past, and nothing announces the moment it does. Enumerating the set converts
"6 failures, same as before" from a memory into a check.

Run `python tests/check_known_failures.py` to verify the live set still equals the set
recorded here. It fails if the set **grows** (a regression) or **shrinks** (something
was fixed and this file was not updated). Neither direction is silent.

**None of these involve `congress_api/features/bill_text/`.** They pre-date the
bill-text branch; verified by running the same suite on the base commit.

## Collection errors (10 files, 0 tests run)

### Undeclared dependency: `fastmcp` (6 files)

```
tests/test_committee_intelligence_hub_bucket.py
tests/test_legislation_hub_bucket.py
tests/test_people_relationships_hub_bucket.py
tests/test_records_communications_hub_bucket.py
tests/test_research_professional_hub_bucket.py
tests/test_voting_political_hub_bucket.py
```

`ModuleNotFoundError: No module named 'fastmcp'`. These import `fastmcp`, which is
not declared in `pyproject.toml` and is not installed. The package under test imports
`mcp.server.mcpserver`, so this looks like test files left behind by a migration off
fastmcp rather than a missing install.

### Stale import: `congress_api.core.services` (4 files)

```
tests/test_email_service.py
tests/test_email_templates.py
tests/test_upgrade_email.py
tests/test_user_creation.py
```

`ModuleNotFoundError: No module named 'congress_api.core.services'`. The module does
not exist anywhere in the tree, so these test a package layout that is gone.

## Test failures (6)

### `'Mock' object is not subscriptable` (4)

```
tests/test_bucket_double_conversion.py::test_committee_intelligence_does_not_double_convert
tests/test_bucket_double_conversion.py::test_records_and_hearings_does_not_double_convert
tests/test_bucket_double_conversion.py::test_research_and_professional_does_not_double_convert
tests/test_bucket_double_conversion.py::test_voting_and_nominations_does_not_double_convert
```

The mock returned by the patched client is indexed by the bucket implementation and
raises `TypeError`, surfacing as `ToolError`. A test-harness problem in the bucket
features, unrelated to their production behavior.

### Async tests with no async plugin (2)

```
tests/test_registration_endpoint.py::test_registration_endpoint
tests/test_registration_endpoint.py::test_health_endpoint
```

`Failed: async def functions are not natively supported`. `pytest-asyncio` is
installed (the bill-text async tests use `@pytest.mark.asyncio`) but no `asyncio_mode`
is configured and these two functions carry no marker.
