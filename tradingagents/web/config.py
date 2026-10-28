"""Validated desk settings; credentials remain in the server environment."""

from __future__ import annotations

import re
from typing import Literal
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
    max_tokens: int | None = Field(default=None, gt=0, strict=True)
    deep_max_total_tokens: int | None = Field(default=None, gt=0, strict=True)
    deep_max_output_tokens: int | None = Field(default=None, gt=0, strict=True)
    deep_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = None
    quick_max_total_tokens: int | None = Field(default=None, gt=0, strict=True)
    quick_max_output_tokens: int | None = Field(default=None, gt=0, strict=True)
    quick_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = None
    max_debate_rounds: int = Field(default=1, ge=1, le=3)
    max_risk_discuss_rounds: int = Field(default=1, ge=1, le=3)
    max_tool_rounds: int = Field(default=8, ge=1, le=20)
    research_concurrency: int = Field(default=1, ge=1, le=100, strict=True)
    research_stop_on_failure: bool = Field(default=False, strict=True)
    research_retries: int = Field(default=10, ge=0, strict=True)
    laya_device: Literal["cpu", "gpu"] = "cpu"
    social_screen_timeout_seconds: int = Field(default=600, ge=1)
    social_screen_max_posts: int = Field(default=100, ge=1)
    selected_analysts: list[Literal["market", "social", "news", "fundamentals"]] = Field(
        default_factory=lambda: ["market", "social", "news", "fundamentals"], min_length=1, max_length=4)

    @model_validator(mode="before")
    @classmethod
    def migrate_output_limit(cls, values):
        if (isinstance(values, dict) and values.get("max_tokens") is not None
                and str(values.get("llm_provider", "codex")).lower() not in {"codex", "chatgpt"}):
            values = dict(values)
            for tier in ("deep", "quick"):
                values.setdefault(f"{tier}_max_output_tokens", values["max_tokens"])
        return values

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
        provider = self.llm_provider.lower()
        for tier in ("deep", "quick"):
            if getattr(self, f"{tier}_max_total_tokens") is not None and provider != "openai_compatible":
                raise ValueError(f"Total token limits are not supported for provider '{provider}'.")
            if getattr(self, f"{tier}_max_output_tokens") is not None and provider in {"codex", "chatgpt"}:
                raise ValueError(f"Output token limits are not supported for provider '{provider}'.")
            if (getattr(self, f"{tier}_reasoning_effort") is not None
                    and provider not in {"codex", "chatgpt", "openai", "openai_compatible"}):
                raise ValueError(f"Reasoning effort is not supported for provider '{provider}'.")
        return self
