"""Validated desk settings; credentials remain in the server environment."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FANGMAN = ["META", "AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "NFLX"]
MAX_UNIVERSE = 1000


class DeskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: str = Field(default="FANGMAN", min_length=1, max_length=40)
    universe: list[str] = Field(default_factory=lambda: FANGMAN.copy(), min_length=1, max_length=MAX_UNIVERSE)
    allocation_pct: float = Field(default=70, gt=0, le=100)
    max_position_pct: float = Field(default=15, gt=0, le=100)
    max_order_notional: float = Field(default=5000, gt=0, le=1000000)
    reserve_pct: float = Field(default=20, ge=0, lt=100)
    price_buffer_bps: float = Field(default=25, ge=0, le=100)
    llm_provider: str = Field(default="codex", min_length=1, max_length=50)
    deep_think_llm: str = Field(default="gpt-6-sol", min_length=1, max_length=100)
    quick_think_llm: str = Field(default="gpt-6-luna", min_length=1, max_length=100)
    backend_url: str | None = None
    max_debate_rounds: int = Field(default=1, ge=1, le=3)
    max_risk_discuss_rounds: int = Field(default=1, ge=1, le=3)
    max_tool_rounds: int = Field(default=8, ge=1, le=20)

    @field_validator("universe")
    @classmethod
    def symbols(cls, values):
        result = list(dict.fromkeys(v.strip().upper() for v in values))
        if any(not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", v) for v in result):
            raise ValueError("Use US equity symbols, such as AAPL or BRK.B.")
        return result

    @field_validator("name", "llm_provider", "deep_think_llm", "quick_think_llm")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a value; whitespace alone is not valid.")
        return value

    @field_validator("backend_url")
    @classmethod
    def endpoint(cls, value):
        if not value:
            return None
        url = urlsplit(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Model endpoint must be an HTTP(S) URL without credentials or query parameters."
            )
        return value.rstrip("/")

    @model_validator(mode="after")
    def cash_budget(self):
        if self.allocation_pct + self.reserve_pct > 100:
            raise ValueError("Allocation and cash reserve must total no more than 100%.")
        if self.max_position_pct > self.allocation_pct:
            raise ValueError("The single-position limit cannot exceed total invested allocation.")
        return self
