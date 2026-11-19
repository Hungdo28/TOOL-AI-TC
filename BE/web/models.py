from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: Any
    content_type: str = "application/json; charset=utf-8"
    headers: dict[str, str] | None = None

