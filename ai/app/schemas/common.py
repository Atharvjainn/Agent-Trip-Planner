"""
Shared primitives mirrored from packages/shared (root AGENTS.md §5, §6).

Field names are camelCase over the wire. Every model here uses
alias_generator=to_camel, same as every other Pydantic model in this service,
so FastAPI request/response JSON matches the Zod schemas in packages/shared
byte for byte.
"""
from __future__ import annotations

import json
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.config import get_settings


class CamelModel(BaseModel):
    """Base class for every wire-crossing model in this service."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


@lru_cache
def _load_enum(filename: str) -> list[str]:
    settings = get_settings()
    path = settings.shared_enums_dir / filename
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return list(data["values"])


def vibe_tags() -> list[str]:
    return _load_enum("vibes.json")


def trip_statuses() -> list[str]:
    return _load_enum("trip_status.json")


def budget_categories() -> list[str]:
    return _load_enum("budget_categories.json")


class Money(CamelModel):
    """
    root AGENTS.md §6: represent money as integer minor units + ISO-4217
    currency. Never a bare float. This mirrors the original-provider price;
    apps/api is responsible for attaching the converted price + fxRate +
    fxAt on the Selection row — this service only ever emits amounts in the
    currency it actually observed (the provider's or the rules engine's).
    """

    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class GeoPoint(CamelModel):
    lat: float
    lng: float


class ProviderRef(CamelModel):
    """Identifies the exact SerpApi object a result came from, for KG MERGE
    keys and for the frontend's provider deep link (we don't book, §1)."""

    provider: str = "serpapi"
    id: str
    deep_link: str | None = None


class VibeScore(CamelModel):
    vibe: str
    score: float = Field(ge=0, le=1)

    @field_validator("vibe")
    @classmethod
    def _known_vibe(cls, v: str) -> str:
        allowed = vibe_tags()
        if v not in allowed:
            raise ValueError(f"unknown vibe tag {v!r}, must be one of {allowed}")
        return v


class JobError(CamelModel):
    code: str
    message: str
    fallback_used: bool = False


# ISO 4217 zero-decimal currencies
_ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "MGA", "PYG",
    "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"
}
# ISO 4217 three-decimal currencies
_THREE_DECIMAL_CURRENCIES = {
    "BHD", "IQD", "JOD", "KWD", "OMR", "TND"
}

def get_currency_exponent(currency: str) -> int:
    curr = (currency or "INR").upper().strip()
    if curr in _ZERO_DECIMAL_CURRENCIES:
        return 0
    if curr in _THREE_DECIMAL_CURRENCIES:
        return 3
    return 2

def float_to_money_dict(amount: any, currency: str = "INR") -> dict | None:
    if amount is None or not isinstance(amount, (int, float)):
        return None
    curr = (currency or "INR").upper().strip()
    exp = get_currency_exponent(curr)
    amount_minor = int(round(float(amount) * (10 ** exp)))
    return {"amountMinor": amount_minor, "currency": curr}
