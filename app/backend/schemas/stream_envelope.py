from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StreamEnvelope(BaseModel):
    event: str
    payload: dict[str, Any]
