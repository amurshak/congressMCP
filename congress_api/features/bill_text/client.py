"""GovInfo client and Congress.gov version resolution for bill text."""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from mcp.server.mcpserver import Context

from ...core.api_config import API_KEY
from ...core.client_handler import get_app_context


logger = logging.getLogger(__name__)

GOVINFO_BASE_URL = "https://api.govinfo.gov"
MAX_XML_BYTES = 50 * 1024 * 1024
VERSION_PRECEDENCE = {
    "ih": 10,
    "is": 10,
    "rih": 10,
    "ris": 10,
    "rh": 20,
    "rs": 20,
    "rch": 20,
    "rcs": 20,
    "pcs": 30,
    "pap": 30,
    "eh": 40,
    "es": 40,
    "eah": 40,
    "eas": 40,
    "cph": 50,
    "cps": 50,
    "enr": 90,
}
VERSION_TYPE_MAP = {
    "introduced in house": "ih",
    "introduced in senate": "is",
    "referred in house": "rih",
    "referred in senate": "ris",
    "reported in house": "rh",
    "reported in senate": "rs",
    "engrossed in house": "eh",
    "engrossed in senate": "es",
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
    xml_bytes: bytes


class BillTextError(Exception):
    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None, remediation: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
        self.remediation = remediation


async def resolve_and_fetch_bill_text(
    ctx: Context,
    congress: int,
    bill_type: str,
    number: int,
    version: str | None,
) -> ResolvedBillText:
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
        fetched = await fetch_govinfo_package(package_id)
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
            fetched = await fetch_govinfo_package(package_id)
            note = base_note
            if candidate != candidates[0]:
                substitution = (
                    f"Latest listed version {candidates[0].code} was unavailable from GovInfo; "
                    f"fell back to {candidate.code}."
                )
                note = f"{base_note} {substitution}" if base_note else substitution
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
        raise BillTextError(
            "govinfo_key_rejected",
            "The existing api.data.gov key was rejected by GovInfo.",
            {"status_code": response.status_code},
            "api.congress.gov and api.govinfo.gov normally share one api.data.gov key; set GOVINFO_API_KEY to override.",
        )
    if response.status_code >= 400:
        raise BillTextError(
            "congress_unavailable",
            "Congress.gov was unreachable and the GovInfo search fallback also failed.",
            {"status_code": response.status_code},
            "Retry later, or pin an explicit version if known.",
        )
    prefix = f"BILLS-{congress}{bill_type.lower()}{number}"
    pattern = re.compile(rf"^{re.escape(prefix)}([a-z]+)$", re.IGNORECASE)
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


async def congress_text_versions(ctx: Context, congress: int, bill_type: str, number: int) -> list[TextVersion]:
    app_ctx = ctx.request_context.lifespan_context if ctx is not None else get_app_context()
    response = await app_ctx.client.get(
        f"/bill/{congress}/{bill_type}/{number}/text",
        params={"format": "json", "api_key": app_ctx.api_key},
    )
    if response.status_code == 404:
        raise BillTextError(
            "bill_not_found",
            f"No such bill: {congress} {bill_type.upper()} {number}.",
            None,
            "Check congress, bill_type, and number.",
        )
    if response.status_code >= 400:
        raise BillTextError(
            "congress_unavailable",
            "Congress.gov text-version metadata could not be retrieved.",
            {"status_code": response.status_code},
            "Retry later, or pin an explicit version if known.",
        )
    data = response.json()
    text_versions = data.get("textVersions") or data.get("text_versions") or []
    versions = []
    for item in text_versions:
        type_label = str(item.get("type") or item.get("typeLabel") or "")
        date = str(item.get("date") or item.get("formattedDate") or "")
        code = _version_code_from_item(congress, bill_type, number, item) or VERSION_TYPE_MAP.get(type_label.casefold())
        if code:
            versions.append(TextVersion(code=code.lower(), date=date, type_label=type_label))
    if not versions:
        raise BillTextError(
            "version_not_available",
            f"{bill_type.upper()} {number} exists but has no text versions.",
            {"available_versions": []},
            "Retry later or verify the bill has published text.",
        )
    return versions


async def fetch_govinfo_package(package_id: str) -> tuple[str | None, bytes]:
    api_key = os.getenv("GOVINFO_API_KEY") or API_KEY or ""
    # follow_redirects is handled manually so the api_key header is only ever
    # sent to api.govinfo.gov and never forwarded across a redirect to a CDN/S3.
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0), follow_redirects=False) as client:
        summary = await _govinfo_request(client, "GET", f"{GOVINFO_BASE_URL}/packages/{package_id}/summary", api_key)
        if summary.status_code == 404:
            raise BillTextError("govinfo_not_found", f"GovInfo package {package_id} was not found.")
        if summary.status_code in {401, 403}:
            raise BillTextError(
                "govinfo_key_rejected",
                "The existing api.data.gov key was rejected by GovInfo.",
                {"status_code": summary.status_code},
                "api.congress.gov and api.govinfo.gov normally share one api.data.gov key; set GOVINFO_API_KEY to override.",
            )
        if summary.status_code >= 400:
            raise BillTextError("govinfo_unavailable", "GovInfo package summary could not be retrieved.", {"status_code": summary.status_code})
        data = summary.json()
        last_modified = data.get("lastModified") or data.get("lastModifiedDate")
        xml_url = _xml_url_from_summary(data)
        if not xml_url:
            raise BillTextError("bill_dtd_unavailable", f"GovInfo package {package_id} did not include a Bill DTD XML link.")
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
        return last_modified, b"".join(chunks)


def _is_govinfo_host(url: str) -> bool:
    return (httpx.URL(url).host or "").lower() == "api.govinfo.gov"


async def _govinfo_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    api_key: str,
    stream: bool = False,
) -> httpx.Response:
    """Request with bounded 429/503 backoff, sending the key as an X-Api-Key
    header (never a logged query param) and only to api.govinfo.gov."""
    delay = 1.0
    last_response = None
    for _ in range(4):
        response = await _follow_with_key(client, method, url, api_key, stream=stream)
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
) -> httpx.Response:
    current = url
    for _ in range(max_redirects + 1):
        headers = {"X-Api-Key": api_key} if api_key and _is_govinfo_host(current) else None
        request = client.build_request(method, current, headers=headers)
        response = await client.send(request, stream=stream)
        if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
            location = str(httpx.URL(current).join(response.headers["location"]))
            await response.aclose()
            if response.status_code == 303:
                method = "GET"
            current = location
            continue
        return response
    return response


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        try:
            return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return None


def _xml_url_from_summary(data: dict[str, Any]) -> str | None:
    download = data.get("download") or {}
    for key in ("xmlLink", "xml"):
        value = download.get(key)
        if isinstance(value, str):
            return value
    for key in ("modsLink",):
        value = download.get(key)
        if isinstance(value, str) and value.lower().endswith(".xml"):
            return value
    for value in download.values():
        if isinstance(value, str) and value.lower().endswith(".xml"):
            return value
    return None


def _version_code_from_item(congress: int, bill_type: str, number: int, item: dict[str, Any]) -> str | None:
    payload = str(item)
    pattern = rf"BILLS-{congress}{re.escape(bill_type)}{number}([a-z0-9]+)"
    match = re.search(pattern, payload, re.IGNORECASE)
    return match.group(1) if match else None


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
            VERSION_PRECEDENCE.get(item.code, 0),
            item.date or "",
            _inverse_lex_key(item.code),
        ),
        reverse=True,
    )


def package_id_for(congress: int, bill_type: str, number: int, version: str) -> str:
    return f"BILLS-{congress}{bill_type.lower()}{number}{version.lower()}"


def govinfo_details_url(package_id: str) -> str:
    return f"https://www.govinfo.gov/app/details/{package_id}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _inverse_lex_key(value: str) -> str:
    return "".join(chr(255 - ord(char)) for char in value)
