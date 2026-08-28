"""Q11 local snippets for search_bills (govinfo-search-spec Addendum 4 item 1).

Two composable modes, both as ruled:

  (a) opportunistic, always on, CACHE-ONLY -- a hit whose fronted version
      package is already in the persistent bill-text cache gets a snippet for
      free, zero network;
  (b) opt-in bounded fetch -- ``snippet_fetch: N`` (default 0, hard cap 5)
      downloads-and-parses the top-N *uncached* hits in rank order and leaves
      them enrolled for the follow-up reads a research session makes anyway
      (requested warming per Q8, not speculation).

Localization is PER-TERM, not phrase: GovInfo ANDs raw words while FTS5
matches stemmed phrases, so a genuine upstream hit can fail local phrase
localization; querying the index with each text term separately narrows the
gap. Fielded operators, booleans, and wildcards are stripped -- they are
upstream query language, not text to localize.

The tri-state is structural, and it is the make-or-break (per the ruling
verbatim: if it cannot be kept clean, the feature does not ship):

  localized      -> ``snippet_status: "localized"`` + a ``snippet`` object
  not localized  -> ``snippet_status: "not_localized"`` + ``snippet: null``
                    (attempted against cached text; the terms did not match)
  not attempted  -> BOTH fields absent (uncached and no fetch budget, cache
                    disabled, no text terms to localize, or the opt-in fetch
                    failed before any text existed to attempt against)

An empty-string snippet is UNREPRESENTABLE: the ``LocalizedSnippet`` model
(min-length-1 text, min-length-1 match_contexts) is the only constructor of
the ``snippet`` object, enforced at the serialization layer, not by
convention -- a construction failure downgrades to ``not_localized``.

The amendatory-trap disclosure travels with the snippet: every snippet
carries the matched unit's ``section_id`` and ``match_contexts``, and a
snippet whose matched segment is quoted has the quoted text delimited in the
snippet string itself (the index's own rendering). The tool description
states that ``"quoted"`` governs -- text the bill may be striking or
inserting, not what current law says.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

SNIPPET_FETCH_CAP = 5

# Upstream query-language tokens that are not localizable text: fielded terms
# (field:value, field:"quoted value", field:range(a,b)) and bare booleans.
_FIELDED_RE = re.compile(r'\b[A-Za-z]+:(?:"[^"]*"|range\([^)]*\)|\S+)')
_QUOTED_RE = re.compile(r'"([^"]+)"')
_BOOLEANS = {"and", "or", "not"}


class LocalizedSnippet(BaseModel):
    """The only constructor of a serialized snippet object. Empty text (and
    an empty match_contexts) are unrepresentable by model validation."""
    text: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    match_contexts: "list[str]" = Field(min_length=1)


def clamp_snippet_fetch(value: Any) -> "tuple[int, Optional[str]]":
    """``snippet_fetch`` normalized: None/0 -> 0; 1..5 pass; above the hard
    cap clamps with an advisory (the clamp_limit pattern); negative or
    non-integer raises the tool's invalid-parameter error."""
    from ....core.exceptions import CommonErrors, CongressionalAPIError

    if value is None:
        return 0, None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CongressionalAPIError(CommonErrors.invalid_parameter(
            "snippet_fetch", repr(value),
            "snippet_fetch must be an integer between 0 and 5."))
    if value < 0:
        raise CongressionalAPIError(CommonErrors.invalid_parameter(
            "snippet_fetch", str(value),
            "snippet_fetch must be an integer between 0 and 5."))
    if value > SNIPPET_FETCH_CAP:
        return SNIPPET_FETCH_CAP, (
            f"snippet_fetch clamped to {SNIPPET_FETCH_CAP} "
            f"(requested {value}; the cap bounds per-call downloads).")
    return value, None


def extract_text_terms(keywords: str) -> "list[str]":
    """The query's TEXT terms, for per-term localization: quoted phrases are
    one term each; fielded operators, booleans, exclusions (``-term`` and the
    operand of a ``NOT``), and wildcard characters are upstream query
    language and are dropped -- an excluded term is text the matching
    document must NOT contain, so localizing it would be wrong twice."""
    rest = _FIELDED_RE.sub(" ", keywords)
    # Excluded phrases drop before phrase extraction sees them.
    rest = re.sub(r'(?:\bNOT\s+|-)"[^"]*"', " ", rest, flags=re.IGNORECASE)
    terms: "list[str]" = []
    for phrase in _QUOTED_RE.findall(rest):
        cleaned = " ".join(phrase.split())
        if re.search(r"[A-Za-z0-9]", cleaned):
            terms.append(cleaned)
    rest = _QUOTED_RE.sub(" ", rest)
    skip_next = False
    for token in rest.split():
        if skip_next:
            skip_next = False
            continue
        if token.lower() == "not":
            skip_next = True
            continue
        if token.lower() in _BOOLEANS or token.startswith("-"):
            continue
        cleaned = token.replace("*", "").replace("?", "")
        if re.search(r"[A-Za-z0-9]", cleaned):
            terms.append(cleaned)
    return terms


def _localize(hit: "dict[str, Any]", index: Any, terms: "list[str]") -> None:
    """Attempt per-term localization against one cached package's index and
    stamp the structural tri-state onto the hit (this function only ever
    produces the two ATTEMPTED states)."""
    ranked = index.search(terms, 1)
    if ranked:
        best = ranked[0]
        try:
            snippet = LocalizedSnippet(
                text=best.snippet,
                section_id=best.unit.section_id,
                match_contexts=best.match_contexts,
            )
        except ValidationError:
            # The unrepresentable states (empty snippet text, no contexts)
            # downgrade structurally rather than shipping a hollow object.
            hit["snippet_status"] = "not_localized"
            hit["snippet"] = None
            return
        hit["snippet_status"] = "localized"
        hit["snippet"] = snippet.model_dump()
    else:
        hit["snippet_status"] = "not_localized"
        hit["snippet"] = None


async def attach_snippets(bills: "list[dict[str, Any]]", keywords: str,
                          snippet_fetch: int) -> int:
    """Enrich corpus hits (in rank order) with the Q11 snippet fields.
    Returns the number of packages fetched-and-enrolled (<= snippet_fetch).

    Cache-only unless ``snippet_fetch`` grants budget; a hit left untouched
    carries NEITHER field (the not-attempted state). All failures are
    per-hit and non-fatal: snippets are an enrichment, never a reason to
    fail the search response.
    """
    from ...bill_text.service import get_store

    store = get_store()
    if store is None:
        return 0
    terms = extract_text_terms(keywords)
    if not terms:
        # Nothing to localize (pure fielded query): not attempted, by design.
        return 0

    fetched = 0
    budget = snippet_fetch
    for hit in bills:
        package_id = hit.get("package_id")
        if not package_id:
            continue
        index = None
        try:
            index = store.open(package_id, None)
        except Exception as exc:  # noqa: BLE001 -- enrichment must not fail the search
            logger.warning("snippet cache open failed for %s: %s", package_id, exc)
        if index is None:
            if budget <= 0:
                continue
            budget -= 1
            index = await _fetch_and_enroll(store, hit, package_id)
            if index is None:
                # The opt-in fetch failed: no text ever existed locally to
                # attempt against, so the hit stays in the ABSENT state.
                continue
            fetched += 1
        try:
            _localize(hit, index, terms)
        except Exception as exc:  # noqa: BLE001
            logger.warning("snippet localization failed for %s: %s", package_id, exc)
            hit.pop("snippet_status", None)
            hit.pop("snippet", None)
    return fetched


async def _fetch_and_enroll(store: Any, hit: "dict[str, Any]",
                            package_id: str) -> Any:
    """Download, parse, and publish one package into the persistent cache
    (the Q8-sanctioned requested warming), returning its index or None."""
    from ...bill_text.client import fetch_govinfo_package
    from ...bill_text.parser import parse_bill_xml

    try:
        last_modified, data = await fetch_govinfo_package(package_id)
        parsed = parse_bill_xml(data, package_id,
                                str(hit.get("version") or ""), last_modified)
        index, _ = store.build_and_publish(parsed, last_modified=last_modified)
        return index
    except Exception as exc:  # noqa: BLE001
        logger.warning("snippet_fetch failed for %s: %s", package_id, exc)
        return None
