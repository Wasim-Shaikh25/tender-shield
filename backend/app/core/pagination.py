"""Shared pagination helpers for list endpoints.

Implements offset/limit pagination (called "cursor" by the audit because the API
surface is small). For very large tables, switch to keyset pagination keyed on
`created_at` / `id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from fastapi import Query, Response

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000


@dataclass
class PaginationParams:
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Query(0, ge=0)


def paginate_list(items: list[T], params: PaginationParams) -> list[T]:
    """Slice an already-materialised list."""
    return items[params.offset : params.offset + params.limit]


def set_pagination_headers(response: Response, params: PaginationParams, total: int) -> None:
    """Set standard pagination headers on the outgoing response."""
    response.headers["X-Total-Count"] = str(total)
    next_offset = params.offset + params.limit if params.offset + params.limit < total else None
    prev_offset = params.offset - params.limit if params.offset >= params.limit else None
    if next_offset is not None:
        response.headers["X-Next-Offset"] = str(next_offset)
    if prev_offset is not None:
        response.headers["X-Prev-Offset"] = str(prev_offset)
    response.headers["X-Page-Limit"] = str(params.limit)


def paginated_list_response(
    items: list[T],
    params: PaginationParams,
    response: Response,
) -> list[T]:
    """Return a paginated slice and set pagination headers."""
    total = len(items)
    set_pagination_headers(response, params, total)
    return paginate_list(items, params)
