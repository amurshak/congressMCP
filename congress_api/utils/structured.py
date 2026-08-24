"""Carrier for structured items alongside formatted markdown.

Impl functions across congress_api/features return pre-formatted markdown
strings. The response converters that build the typed Pydantic responses
only ever saw that markdown, so they guessed `results_count` with regexes
and always emitted empty typed lists (issue #55).

StructuredText lets an impl hand the converter the real, cleaned item dicts
it already holds at format time — without changing any function signature:
it IS a str (every existing consumer, test, and `-> str` annotation keeps
working), it just also carries `.structured_items` and `.item_kind`.

Usage in an impl, immediately before the existing return:

    return structured("\n".join(result), "member", filtered_members)

Converters read the attributes with getattr(...) and fall back to the
legacy regex path for plain strings.
"""
from typing import Any, Dict, List, Optional


class StructuredText(str):
    """A str subclass that also carries the structured items behind it."""

    item_kind: Optional[str]
    structured_items: List[Dict[str, Any]]

    def __new__(cls, text: str, item_kind: Optional[str] = None,
                items: Optional[List[Dict[str, Any]]] = None):
        obj = super().__new__(cls, text)
        obj.item_kind = item_kind
        obj.structured_items = [i for i in (items or []) if isinstance(i, dict)]
        return obj


def structured(text: str, item_kind: str,
               items: Optional[List[Dict[str, Any]]] = None) -> StructuredText:
    """Attach real item dicts (and their kind) to a formatted response.

    `items` is the cleaned/deduplicated/limited list the markdown was
    rendered from — pass exactly what was formatted, so the typed list and
    the summary can never disagree. For single-record detail responses pass
    a one-element list.
    """
    return StructuredText(text, item_kind, items)
