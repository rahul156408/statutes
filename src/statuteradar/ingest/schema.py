from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Jurisdiction = Literal["EU", "IN", "US-CA"]
Instrument = Literal["GDPR", "DPDP", "DPDP-Rules", "CCPA"]
Kind = Literal["operative", "definition", "recital", "schedule"]


class Chunk(BaseModel):
    """One retrievable unit of legal text. This is the contract for Phases 2-8."""

    chunk_id: str
    instrument: Instrument
    jurisdiction: Jurisdiction
    kind: Kind
    unit_id: str                      # the Article / Section / Rule this chunk belongs to
    citation: str                     # e.g. "GDPR Art. 17(1)(a)"
    hierarchy: list[str]              # chapter > unit > paragraph > point
    title: str | None = None
    text: str = Field(min_length=1)
    token_count: int
    parent_instrument: str | None = None   # "DPDP" for DPDP-Rules chunks
    commencement_phase: int | None = None  # DPDP-Rules only (1, 2 or 3), see config.py
    source_file: str
    source_sha256: str
    char_start: int                   # offsets into data/interim/<key>.txt
    char_end: int