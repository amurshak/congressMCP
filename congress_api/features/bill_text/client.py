"""GovInfo client and Congress.gov version resolution for bill text."""

from __future__ import annotations

import asyncio
import logging
import contextvars
import os
import time
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
from mcp.server.mcpserver import Context

from ...core.api_config import API_KEY
from ...core.client_handler import make_api_request
from ...core.retry_timing import parse_retry_after as _retry_after


logger = logging.getLogger(__name__)

GOVINFO_BASE_URL = "https://api.govinfo.gov"
MAX_XML_BYTES = 50 * 1024 * 1024
# The one version-code alphabet, shared by both enumeration paths (spec §3):
# digit-suffixed reissues (pcs2, rh2, eas2) are valid codes, but the code must
# start with a letter so a longer bill number sharing the queried prefix
# (BILLS-119hr12345eh matched against bill 1234) cannot bleed digits into it.
VERSION_CODE_PATTERN = r"[a-z][a-z0-9]*"
# Version codes: (precedence rank, category). Complete against GovInfo's published
# list of 53 bill version codes (govinfo.gov/help/bills), not a 17-code subset.
#
# WHY A CATEGORY AND NOT JUST A RANK (F1). "Latest" means *most authoritative text*,
# not *most recent artifact*, and for three classes those diverge -- a single linear
# scale cannot express the difference, so a later editor "correcting" a rank toward
# chronological order would silently reintroduce the bug the rank was placed to avoid.
# The category records the intent:
#
#   TEXT_STAGE     -- a real stage of the legislative text; rank orders them.
#   REISSUE        -- re-issues an earlier stage and SUPERSEDES it (rank sits just
#                     above the stage it re-issues). `renr` outranking `enr` is one of
#                     the two correctness bugs F1 names: at precedence 0 it sorted last
#                     and `enr` won, returning superseded text as final.
#   ADMINISTRATIVE -- chronologically later but textually identical to the stage it
#                     annotates (sponsor changes, print orders). MUST NOT displace that
#                     stage, so it ranks below every text stage: when the annotated
#                     stage is present it wins, which is the correct pick since the two
#                     carry the same text.
#   NEGATIVE       -- chronologically LAST and NOT authoritative (failed passage, laid
#                     on table, indefinitely postponed, vitiated). Must never be
#                     "latest", so it ranks below everything -- including an unknown
#                     code, because an unknown code might be a new authoritative stage
#                     whereas these are known not to be.
#
# Ranks from the original 17-code table are preserved exactly; the 36 additions are
# placed around them. `ath`/`ats` at 80 fixes F1's second correctness bug: simple and
# concurrent resolutions never reach `enr`, so with those codes absent from the table
# EVERY agreed-to resolution resolved to `ih`. Agreed-to IS terminal for a resolution,
# and 80 keeps `enr` winning wherever both somehow appear.
TEXT_STAGE = "text_stage"
REISSUE = "reissue"
ADMINISTRATIVE = "administrative"
NEGATIVE = "negative"

# Rank given to a code GPO adds after this table was written. Above NEGATIVE (an
# unknown stage may be authoritative; a failed-passage one is known not to be) and
# below every known text stage. Codes landing here also fire the §3 unknown-code
# WARNING and a caller-facing version_resolution_note.
UNKNOWN_PRECEDENCE = 0

VERSION_CODES: dict[str, tuple[int, str]] = {
    # --- not authoritative at any chronological position -------------------------
    "fph": (-10, NEGATIVE),    # failed passage (House)
    "fps": (-10, NEGATIVE),    # failed passage (Senate)
    "fah": (-10, NEGATIVE),    # failed amendment (House)
    "lth": (-10, NEGATIVE),    # laid on table (House)
    "lts": (-10, NEGATIVE),    # laid on table (Senate)
    "iph": (-10, NEGATIVE),    # indefinitely postponed (House)
    "ips": (-10, NEGATIVE),    # indefinitely postponed (Senate)
    "pav": (-10, NEGATIVE),    # previous action vitiated
    # --- annotate a stage without changing its text ------------------------------
    "ash": (5, ADMINISTRATIVE),   # House sponsors/cosponsors added or withdrawn
    "sas": (5, ADMINISTRATIVE),   # additional sponsors (Senate)
    "sc": (5, ADMINISTRATIVE),    # sponsor change
    "as": (5, ADMINISTRATIVE),    # Senate amendment ordered to be printed
    "oph": (5, ADMINISTRATIVE),   # ordered to be printed (House)
    "ops": (5, ADMINISTRATIVE),   # ordered to be printed (Senate)
    "pwah": (5, ADMINISTRATIVE),  # ordered to be printed with House amendment
    "rhuc": (5, ADMINISTRATIVE),  # returned to House by unanimous consent
    # --- introduced / referred in the originating chamber ------------------------
    "ih": (10, TEXT_STAGE),
    "is": (10, TEXT_STAGE),
    "rih": (10, TEXT_STAGE),   # referred to House committee with instructions
    "ris": (10, TEXT_STAGE),
    "rth": (10, TEXT_STAGE),   # referred to committee (House)
    "rts": (10, TEXT_STAGE),
    "rah": (15, TEXT_STAGE),   # referred WITH amendments -- text has moved past introduced
    "ras": (15, TEXT_STAGE),
    "cdh": (15, TEXT_STAGE),   # committee discharged -- past committee, text usually as introduced
    "cds": (15, TEXT_STAGE),
    # --- reported ----------------------------------------------------------------
    "rh": (20, TEXT_STAGE),
    "rs": (20, TEXT_STAGE),
    "rch": (20, TEXT_STAGE),   # referred to a different/additional House committee
    "rcs": (20, TEXT_STAGE),
    # --- calendar / print-as-passed ----------------------------------------------
    "pch": (30, TEXT_STAGE),   # placed on calendar (House) -- sibling of pcs
    "pcs": (30, TEXT_STAGE),
    "pap": (30, TEXT_STAGE),   # printed as passed
    "pp": (30, TEXT_STAGE),    # public print -- peer of pap (§3)
    # --- engrossed / passed one chamber ------------------------------------------
    "eh": (40, TEXT_STAGE),
    "es": (40, TEXT_STAGE),
    "eah": (40, TEXT_STAGE),
    "eas": (40, TEXT_STAGE),
    "eph": (40, TEXT_STAGE),   # engrossed and deemed passed by House
    "reah": (45, REISSUE),     # re-engrossed amendment (House) -- supersedes eah
    "res": (45, REISSUE),      # re-engrossed amendment (Senate) -- supersedes eas/es
    "cph": (50, TEXT_STAGE),
    "cps": (50, TEXT_STAGE),
    # --- received in the second chamber: carries the FIRST chamber's passed text,
    #     so these sit AFTER engrossment, not with ih/is (§3).
    "rdh": (55, TEXT_STAGE),   # received in House from Senate
    "rds": (55, TEXT_STAGE),
    "rfh": (55, TEXT_STAGE),   # referred to House committee after receipt from Senate
    "rfs": (55, TEXT_STAGE),
    "hdh": (55, TEXT_STAGE),   # held at House desk after receipt from Senate
    "hds": (55, TEXT_STAGE),
    # --- terminal ----------------------------------------------------------------
    "ath": (80, TEXT_STAGE),   # agreed to by House -- TERMINAL for a simple/concurrent resolution
    "ats": (80, TEXT_STAGE),   # agreed to by Senate
    "enr": (90, TEXT_STAGE),
    "renr": (95, REISSUE),     # re-enrolled -- supersedes enr
}
VERSION_PRECEDENCE = {code: rank for code, (rank, _) in VERSION_CODES.items()}
VERSION_CATEGORY = {code: category for code, (_, category) in VERSION_CODES.items()}

VERSION_TYPE_MAP = {
    "introduced in house": "ih",
    "introduced in senate": "is",
    "referred in house": "rih",
    "referred in senate": "ris",
    "reported in house": "rh",
    "reported in senate": "rs",
    "engrossed in house": "eh",
    "engrossed in senate": "es",
    "engrossed amendment house": "eah",
    "engrossed amendment senate": "eas",
    "considered and passed house": "cph",
    "considered and passed senate": "cps",
    "placed on calendar house": "pch",
    "placed on calendar senate": "pcs",
    "agreed to house": "ath",
    "agreed to senate": "ats",
    "public print": "pp",
    "printed as passed": "pap",
    "enrolled bill": "enr",
    "enrolled": "enr",
}


@dataclass(frozen=True)
class TextVersion:
    code: str
    date: str
    type_label: str


@dataclass(frozen=True)
class ResolvedBillText:
    package_id: str
    version: str
    version_resolved_at: str
    version_resolution_note: str | None
    last_modified: str | None
    # None when the caller's skip_download hook declined the XML (a fresh cached
    # index exists for this package at this lastModified -- spec §10), so only
    # the GovInfo package summary was fetched.
    xml_bytes: bytes | None


class BillTextError(Exception):
    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None, remediation: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.remediation = remediation


SkipDownload = Callable[[str, "str | None"], bool]

# Seconds spent in the GovInfo XML download leg(s) during the current call, or
# None when no download ran. The service reads it to report timing.download_ms
# separately from resolution (§9: null a leg that did not run). Set by
# fetch_govinfo_package; reset by the service before each call.
DOWNLOAD_SECONDS: contextvars.ContextVar[float | None] = contextvars.ContextVar("bill_text_download_seconds", default=None)

# Error codes that mean "the network / upstream is unavailable" as opposed to
# "the bill or version does not exist". These -- and raw httpx transport errors
# -- are what the §10 offline rows key on.
OFFLINE_CODES = frozenset({"congress_unavailable", "govinfo_unavailable", "govinfo_versions_unavailable"})


def is_offline_error(exc: BaseException) -> bool:
    if isinstance(exc, BillTextError):
        return exc.code in OFFLINE_CODES
    return isinstance(exc, httpx.HTTPError)


async def resolve_and_fetch_bill_text(
    ctx: Context,
    congress: int,
    bill_type: str,
    number: int,
    version: str | None,
    skip_download: SkipDownload | None = None,
) -> ResolvedBillText:
    """Resolve the version, confirm the GovInfo package exists, and fetch its XML.

    ``skip_download(package_id, last_modified)`` -- when it returns True the XML
    download is skipped and ``xml_bytes`` is None; the package summary (which
    carries lastModified and proves the package exists, so the fallback-to-next-
    version behavior is unchanged) is still fetched. This is how the persistent
    cache serves a warm index without re-downloading the document.
    """
    bill_type = bill_type.lower()
    versions = await _resolve_versions(ctx, congress, bill_type, number)
    if version:
        code = version.lower()
        if code not in {item.code for item in versions}:
            raise BillTextError(
                "version_not_available",
                f"{bill_type.upper()} {number} exists but has no '{code}' version.",
                {"available_versions": sorted(item.code for item in versions)},
                "Retry with one of the listed versions, or omit version.",
            )
        package_id = package_id_for(congress, bill_type, number, code)
        fetched = await _fetch_package(package_id, skip_download)
        return ResolvedBillText(
            package_id=package_id,
            version=code,
            version_resolved_at=utc_now(),
            version_resolution_note=None,
            last_modified=fetched[0],
            xml_bytes=fetched[1],
        )

    candidates = order_versions(versions)
    # Surface version-resolution uncertainty to the CALLER (a model), not only the
    # operator log, whenever the list held an unrecognized code (spec §3). The WARNING
    # in order_versions is the operator signal; this note is the consumer signal --
    # both, because a model answering from a silently-older version is a wrong answer
    # inside a success envelope, the worst failure class.
    unknown_codes = sorted({item.code for item in versions if item.code not in VERSION_PRECEDENCE})
    base_note = None
    if versions and all(item.code not in VERSION_PRECEDENCE for item in versions):
        # Every code unknown -> order_versions fell back to date-primary; the whole
        # "latest" pick rests on dates alone.
        base_note = (
            "No known version-precedence codes among the listed versions; "
            "ordered by date alone, so 'latest' may be unreliable. Pass an explicit "
            "version= to bypass."
        )
    elif unknown_codes:
        # Some codes unknown -> they got precedence 0 and sorted LAST. If one denotes a
        # newer stage than the chosen version, a genuinely older version just won. Unlike
        # the all-unknown case this otherwise resolves silently, so §3 requires disclosing
        # it to the caller by name -- this is the more dangerous asymmetry, now closed.
        base_note = (
            f"Unrecognized version code(s) {unknown_codes} were listed and sorted last; "
            f"if one denotes a newer stage than '{candidates[0].code}', this may not be the "
            "latest version. Pass an explicit version= to override."
        )
    errors = []
    for candidate in candidates:
        package_id = package_id_for(congress, bill_type, number, candidate.code)
        try:
            fetched = await _fetch_package(package_id, skip_download)
            parts = [base_note] if base_note else []
            if candidate != candidates[0]:
                parts.append(
                    f"Latest listed version {candidates[0].code} was unavailable from GovInfo; "
                    f"fell back to {candidate.code}."
                )
            # F1: rank keeps a non-text-stage code from displacing real text; this
            # says so out loud when one wins anyway for want of an alternative.
            category_note = _category_note(candidate.code)
            if category_note:
                parts.append(category_note)
            note = " ".join(parts) or None
            return ResolvedBillText(package_id, candidate.code, utc_now(), note, fetched[0], fetched[1])
        except BillTextError as exc:
            if exc.code != "govinfo_not_found":
                raise
            errors.append(candidate.code)
    raise BillTextError(
        "govinfo_versions_unavailable",
        "Congress.gov lists text versions, but GovInfo did not return any listed package.",
        {"attempted_versions": errors},
        "Retry later; GovInfo publication can lag Congress.gov metadata.",
    )


async def _fetch_package(package_id: str, skip_download: SkipDownload | None) -> tuple[str | None, bytes | None]:
    # Looked up at call time so tests may replace fetch_govinfo_package; the
    # keyword is passed only when set, so doubles that predate it still work.
    if skip_download is None:
        return await fetch_govinfo_package(package_id)
    return await fetch_govinfo_package(package_id, skip_download=skip_download)


async def _resolve_versions(ctx: Context, congress: int, bill_type: str, number: int) -> list[TextVersion]:
    """Enumerate text versions from congress.gov, falling back to the GovInfo
    search service only when congress.gov is unreachable (spec §3, secondary
    path). A 404 or an empty-but-valid response is definitive and does not fall
    back — those mean "no such bill" / "no published text", not "unavailable"."""
    try:
        return await congress_text_versions(ctx, congress, bill_type, number)
    except BillTextError as exc:
        if exc.code != "congress_unavailable":
            raise
    except httpx.HTTPError:
        pass
    return await govinfo_search_versions(congress, bill_type, number)


def _govinfo_auth_error(api_key: str, status_code: int) -> BillTextError:
    """The 401/403 branch, split by whether a key was sent at all (F31, §9).

    A keyless server must not wear `govinfo_key_rejected`: "the existing key was
    rejected" sends the operator hunting a stale key that never existed. Missing key
    is its own code, naming the variables to set.
    """
    if not api_key:
        return BillTextError(
            "api_key_missing",
            "No api.data.gov key is configured, and GovInfo refused the "
            "unauthenticated request.",
            {"status_code": status_code},
            "Set CONGRESS_API_KEY in the server's environment (api.congress.gov and "
            "api.govinfo.gov share one api.data.gov key), or GOVINFO_API_KEY to use "
            "a separate GovInfo key.",
        )
    return BillTextError(
        "govinfo_key_rejected",
        "The existing api.data.gov key was rejected by GovInfo.",
        {"status_code": status_code},
        "api.congress.gov and api.govinfo.gov normally share one api.data.gov key; set GOVINFO_API_KEY to override.",
    )


async def govinfo_search_versions(congress: int, bill_type: str, number: int) -> list[TextVersion]:
    api_key = os.getenv("GOVINFO_API_KEY") or API_KEY or ""
    headers = {"X-Api-Key": api_key} if api_key else {}
    body = {
        "query": f"collection:BILLS congress:{congress} billtype:{bill_type.lower()} docnumber:{number}",
        "pageSize": 100,
        "offsetMark": "*",
        "sorts": [{"field": "dateIssued", "sortOrder": "DESC"}],
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        response = await client.post(f"{GOVINFO_BASE_URL}/search", json=body, headers=headers)
    if response.status_code in {401, 403}:
        raise _govinfo_auth_error(api_key, response.status_code)
    if response.status_code >= 400:
        raise BillTextError(
            "congress_unavailable",
            "Congress.gov was unreachable and the GovInfo search fallback also failed.",
            {"status_code": response.status_code},
            "Retry later, or pin an explicit version if known.",
        )
    prefix = f"BILLS-{congress}{bill_type.lower()}{number}"
    pattern = re.compile(rf"^{re.escape(prefix)}({VERSION_CODE_PATTERN})$", re.IGNORECASE)
    by_code: dict[str, TextVersion] = {}
    for item in response.json().get("results") or []:
        match = pattern.match(str(item.get("packageId") or ""))
        if not match:
            continue
        code = match.group(1).lower()
        # Results are date-descending, so the first occurrence keeps the newest date.
        by_code.setdefault(code, TextVersion(code=code, date=str(item.get("dateIssued") or ""), type_label=code))
    if not by_code:
        raise BillTextError(
            "bill_not_found",
            f"No such bill: {congress} {bill_type.upper()} {number}.",
            None,
            "Check congress, bill_type, and number.",
        )
    return list(by_code.values())


def govinfo_api_key() -> str:
    """Resolve the GovInfo key by this client's one rule: GOVINFO_API_KEY
    overrides the shared api.data.gov key (CONGRESS_API_KEY). Returns "" when
    neither is configured -- callers decide what keyless means (F31: the
    corpus-search path must answer api_key_missing without sending anything).
    """
    return os.getenv("GOVINFO_API_KEY") or API_KEY or ""


async def govinfo_search_post(
    body: dict[str, Any], *, client: httpx.AsyncClient | None = None
) -> httpx.Response:
    """POST a GovInfo /search request through this module's keyed transport:
    X-Api-Key header (never key-in-query), bounded 429/503 backoff, key sent
    only to api.govinfo.gov. Returns the raw httpx.Response -- status
    classification (200/429/500/...) is the caller's concern, so the
    search_bills failure flow can read exactly the row it landed on.

    ``client`` lets tests (and callers already holding one) inject a
    transport; an injected client is not closed here.
    """
    api_key = govinfo_api_key()
    url = f"{GOVINFO_BASE_URL}/search"
    if client is not None:
        return await _govinfo_request(client, "POST", url, api_key, json_body=body)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=False
    ) as owned:
        return await _govinfo_request(owned, "POST", url, api_key, json_body=body)


async def congress_text_versions(ctx: Context, congress: int, bill_type: str, number: int) -> list[TextVersion]:
    # Go through make_api_request rather than app_ctx.client directly (#15/F21):
    # the wrapper carries the JSON-decode guard -- a congress.gov 200 with an HTML
    # body must become an error dict, not a JSONDecodeError that jumps over the
    # GovInfo fallback -- plus request counting and the shared response cache.
    data = await make_api_request(f"/bill/{congress}/{bill_type}/{number}/text", ctx)
    if "error" in data:
        if data.get("status_code") == 404:
            raise BillTextError(
                "bill_not_found",
                f"No such bill: {congress} {bill_type.upper()} {number}.",
                None,
                "Check congress, bill_type, and number.",
            )
        # Everything else -- a 5xx, a non-JSON 200 body, a network failure -- means
        # "congress.gov did not give us version metadata", which _resolve_versions
        # treats as recoverable via the GovInfo fallback (spec §3).
        raise BillTextError(
            "congress_unavailable",
            "Congress.gov text-version metadata could not be retrieved.",
            {key: data[key] for key in ("status_code", "error") if key in data},
            "Retry later, or pin an explicit version if known.",
        )
    text_versions = data.get("textVersions") or data.get("text_versions") or []
    versions = []
    for item in text_versions:
        type_label = str(item.get("type") or item.get("typeLabel") or "")
        date = str(item.get("date") or item.get("formattedDate") or "")
        code = _version_code_from_item(congress, bill_type, number, item) or VERSION_TYPE_MAP.get(type_label.casefold())
        if code:
            versions.append(TextVersion(code=code.lower(), date=date, type_label=type_label))
        else:
            # §3 step 2: log an unmapped version-type string rather than guessing a
            # code for it. Dropping it silently makes the entry invisible to both the
            # operator and the caller, and a dropped entry can be the newest stage.
            logger.warning(
                "Congress.gov listed a text version whose GovInfo code could not be "
                "derived from its URLs or type label %r; it was excluded from version "
                "resolution.",
                type_label,
            )
    if not versions:
        raise BillTextError(
            "version_not_available",
            f"{bill_type.upper()} {number} exists but has no text versions.",
            {"available_versions": []},
            "Retry later or verify the bill has published text.",
        )
    return versions


async def fetch_govinfo_package(
    package_id: str, *, skip_download: SkipDownload | None = None
) -> tuple[str | None, bytes | None]:
    """GovInfo package summary (lastModified) plus the Bill DTD XML bytes. With
    ``skip_download`` answering True for (package_id, last_modified) the XML leg
    is skipped and the second element is None."""
    api_key = os.getenv("GOVINFO_API_KEY") or API_KEY or ""
    # follow_redirects is handled manually so the api_key header is only ever
    # sent to api.govinfo.gov and never forwarded across a redirect to a CDN/S3.
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0), follow_redirects=False) as client:
        summary = await _govinfo_request(client, "GET", f"{GOVINFO_BASE_URL}/packages/{package_id}/summary", api_key)
        if summary.status_code == 404:
            raise BillTextError("govinfo_not_found", f"GovInfo package {package_id} was not found.")
        if summary.status_code in {401, 403}:
            raise _govinfo_auth_error(api_key, summary.status_code)
        if summary.status_code >= 400:
            raise BillTextError("govinfo_unavailable", "GovInfo package summary could not be retrieved.", {"status_code": summary.status_code})
        data = summary.json()
        last_modified = data.get("lastModified") or data.get("lastModifiedDate")
        xml_url = _xml_url_from_summary(data)
        if not xml_url:
            raise BillTextError("bill_dtd_unavailable", f"GovInfo package {package_id} did not include a Bill DTD XML link.")
        if skip_download is not None and skip_download(package_id, last_modified):
            return last_modified, None
        started = time.perf_counter()
        try:
            download = await _govinfo_request(client, "GET", xml_url, api_key, stream=True)
            if download.status_code >= 400:
                await download.aclose()
                raise BillTextError("govinfo_unavailable", "GovInfo XML download failed.", {"status_code": download.status_code})
            chunks = []
            size = 0
            try:
                async for chunk in download.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_XML_BYTES:
                        raise BillTextError("document_too_large", f"GovInfo XML exceeded {MAX_XML_BYTES} bytes.")
                    chunks.append(chunk)
            finally:
                await download.aclose()
        finally:
            DOWNLOAD_SECONDS.set((DOWNLOAD_SECONDS.get() or 0.0) + (time.perf_counter() - started))
        return last_modified, b"".join(chunks)


def _is_govinfo_host(url: str) -> bool:
    return (httpx.URL(url).host or "").lower() == "api.govinfo.gov"


async def _govinfo_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    api_key: str,
    stream: bool = False,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    """Request with bounded 429/503 backoff, sending the key as an X-Api-Key
    header (never a logged query param) and only to api.govinfo.gov.
    ``json_body`` rides along for POST endpoints (/search); GET callers are
    unchanged."""
    delay = 1.0
    last_response = None
    for _ in range(4):
        response = await _follow_with_key(client, method, url, api_key, stream=stream, json_body=json_body)
        if response.status_code not in {429, 503}:
            return response
        await response.aclose()
        last_response = response
        retry_after = _retry_after(response.headers.get("Retry-After"))
        sleep_for = retry_after if retry_after is not None else delay + random.uniform(0, 0.25)
        await asyncio.sleep(min(sleep_for, 8.0))
        delay = min(delay * 2, 8.0)
    return last_response if last_response is not None else response


async def _follow_with_key(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    api_key: str,
    stream: bool = False,
    max_redirects: int = 5,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    current = url
    for _ in range(max_redirects + 1):
        headers = {"X-Api-Key": api_key} if api_key and _is_govinfo_host(current) else None
        request = client.build_request(method, current, headers=headers, json=json_body)
        response = await client.send(request, stream=stream)
        if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
            location = str(httpx.URL(current).join(response.headers["location"]))
            await response.aclose()
            if response.status_code == 303:
                method = "GET"
                json_body = None
            current = location
            continue
        return response
    # Redirect exhaustion is an explicit error, never a returned response (F22):
    # the last 3xx is already closed, and callers treat any <400 status as a
    # document -- they would crash later on the closed body with the wrong
    # proximate cause. Report the next hop without its query string, which on a
    # CDN/S3 redirect can carry signed tokens.
    next_hop = httpx.URL(current)
    raise BillTextError(
        "govinfo_unavailable",
        f"GovInfo redirect chain exceeded {max_redirects} redirects without reaching a document.",
        {"max_redirects": max_redirects, "next_location": f"{next_hop.scheme}://{next_hop.host}{next_hop.path}"},
        "Retry later; if this persists the GovInfo download endpoint is misbehaving.",
    )


# _retry_after -- Retry-After header parsing -- now lives in
# core/retry_timing.py (issue #58 code review: this copy had no clamp on
# the numeric branch, so a negative/NaN Retry-After fed straight into
# min(sleep_for, 8.0) below, and min() with NaN doesn't clamp). Imported
# above as `_retry_after` so the call site here is unchanged.


def _xml_url_from_summary(data: dict[str, Any]) -> str | None:
    # Only the Bill DTD link (xmlLink / xml) is bill text. The former fallbacks --
    # modsLink, then ANY download value ending in .xml -- would return metadata: MODS
    # and PREMIS are package metadata XML, present on essentially every package, so the
    # catch-all made the bill_dtd_unavailable error below unreachable. A package with
    # no Bill DTD then downloaded its MODS, parse_bill_xml found no <section>, and the
    # caller got a SUCCESS envelope (source_format "bill_dtd", sections_indexed 0, empty
    # TOC, zero hits) instead of the honest error. Return None when there is no Bill DTD
    # link so bill_dtd_unavailable fires.
    download = data.get("download") or {}
    for key in ("xmlLink", "xml"):
        value = download.get(key)
        if isinstance(value, str):
            return value
    return None


def _version_code_from_item(congress: int, bill_type: str, number: int, item: dict[str, Any]) -> str | None:
    # The version code is a structural property of formats[].url -- the GovInfo
    # package id embedded in the download link -- so read exactly that field
    # (F25). Scanning str(item) let a code-shaped string in ANY field win: a
    # prose note mentioning a superseded package id could beat the URL's true
    # code purely on dict order.
    formats = item.get("formats")
    if not isinstance(formats, list):
        return None
    pattern = re.compile(
        rf"BILLS-{congress}{re.escape(bill_type)}{number}({VERSION_CODE_PATTERN})",
        re.IGNORECASE,
    )
    for fmt in formats:
        if not isinstance(fmt, dict):
            continue
        url = fmt.get("url")
        if not isinstance(url, str):
            continue
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def order_versions(versions: list[TextVersion]) -> list[TextVersion]:
    """Order text versions latest-first per spec §3: **precedence-primary**.

    Sort key is (precedence DESC, date DESC, version_code ASC). The legislative
    ordering is intrinsic to the version code (introduced → reported → engrossed →
    enrolled); the date is the weaker, nullable signal and is used only as a
    tie-break *within* a precedence tier (e.g. two engrossed versions). This is
    the fix for A3's residual risk: the prior "null date = most-recent, precedence
    breaks ties" merely inverted the original bug — it floated any dateless
    non-terminal entry (an `ih` congress.gov returns with date=null and no
    enrolled version present) to the top. Making precedence primary makes the null
    irrelevant rather than special-cased: enrolled (90) always outranks an undated
    introduced (10), and a missing date simply sorts last within its own tier.

    Unknown codes get precedence 0, lose to any known code, and are logged loudly
    (a code GPO adds later fails *loud* here, whereas a null date failed silent —
    detectability is what decides precedence-primary). If *every* code is unknown,
    the precedence-0 tie means the date tie-break governs, i.e. we fall back to
    date-primary among them, which resolve_and_fetch_bill_text discloses.
    """
    unknown = sorted({item.code for item in versions if item.code not in VERSION_PRECEDENCE})
    if unknown:
        logger.warning(
            "Unknown bill text version code(s) with no precedence, sorted last: %s", unknown
        )
    return sorted(
        versions,
        key=lambda item: (
            VERSION_PRECEDENCE.get(item.code, UNKNOWN_PRECEDENCE),
            item.date or "",
            _inverse_lex_key(item.code),
        ),
        reverse=True,
    )


def version_category(code: str) -> str | None:
    """Category of a version code, or None if the code is not in the published table."""
    return VERSION_CATEGORY.get(code.lower())


def _category_note(code: str) -> str | None:
    """Disclose a resolved version that is not a normal text stage.

    Rank keeps these from displacing real text, but rank cannot say anything when
    one is nonetheless selected because it is all the bill has. Silence there would
    present a failed-passage or sponsor-change artifact as the bill's latest text,
    which is the same wrong-answer-inside-a-success-envelope class the A3 note
    closes. Fires only for version=None, where the server -- not the caller -- chose.
    """
    category = VERSION_CATEGORY.get(code)
    if category == NEGATIVE:
        return (
            f"Resolved to '{code}', which records a negative or terminated action "
            "(failed passage, laid on table, indefinitely postponed, or vitiated) "
            "rather than authoritative bill text; no authoritative version was listed."
        )
    if category == ADMINISTRATIVE:
        return (
            f"Resolved to '{code}', an administrative version (sponsor or print "
            "annotation) whose text mirrors the stage it annotates rather than "
            "advancing it."
        )
    return None


def package_id_for(congress: int, bill_type: str, number: int, version: str) -> str:
    return f"BILLS-{congress}{bill_type.lower()}{number}{version.lower()}"


def govinfo_details_url(package_id: str) -> str:
    return f"https://www.govinfo.gov/app/details/{package_id}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _inverse_lex_key(value: str) -> str:
    return "".join(chr(255 - ord(char)) for char in value)
