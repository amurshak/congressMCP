"""Bill text retrieval service that reparses and indexes in memory per call."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from mcp.server.mcpserver import Context

from . import trace
from .client import ResolvedBillText, resolve_and_fetch_bill_text
from .index import BillTextIndex
from .parser import ParsedBill, parse_bill_xml


@dataclass
class LoadedBillText:
    resolved: ResolvedBillText
    parsed: ParsedBill
    index: BillTextIndex
    timing: dict[str, float] = field(default_factory=dict)


async def load_bill_text(ctx: Context, congress: int, bill_type: str, number: int, version: str | None) -> LoadedBillText:
    t0 = time.perf_counter()
    resolved = await resolve_and_fetch_bill_text(ctx, congress, bill_type, number, version)
    # Stamp which exact bytes produced this response for replay (debug tracing only;
    # the sha256 is computed solely when CONGRESSMCP_TRACE_DIR is set).
    trace.set_source(resolved.package_id, resolved.version, resolved.xml_bytes)
    t1 = time.perf_counter()
    parsed = parse_bill_xml(resolved.xml_bytes, resolved.package_id, resolved.version, resolved.last_modified)
    t2 = time.perf_counter()
    index = BillTextIndex(parsed)
    t3 = time.perf_counter()
    timing = {
        "fetch_ms": round((t1 - t0) * 1000, 1),
        "parse_ms": round((t2 - t1) * 1000, 1),
        "index_ms": round((t3 - t2) * 1000, 1),
    }
    return LoadedBillText(resolved=resolved, parsed=parsed, index=index, timing=timing)
