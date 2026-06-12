"""
internal_order.py — canonical internal representation of an order.

Every external source (hospital/clinic) is normalized into InternalOrder by its
own intake adapter. Business logic (services.py) only ever reads InternalOrder,
never a source-specific format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class InternalPatient:
    first_name: str
    last_name: str
    mrn: str                       # 6 digits — checked in the adapter's validate()
    date_of_birth: Optional[date] = None


@dataclass(frozen=True)
class InternalProvider:
    name: str
    npi: str                       # 10 digits


@dataclass(frozen=True)
class InternalMedication:
    name: str
    primary_diagnosis: str = ""
    additional_diagnoses: list[str] = field(default_factory=list)
    medication_history: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InternalOrder:
    patient: InternalPatient
    provider: InternalProvider
    medication: InternalMedication
    patient_records: str = ""

    # provenance — which source this came from and its native id
    source: str = ""               # e.g. "react_frontend", "clinic_b"
    source_order_id: str = ""      # native order id at the source

    # Original payload, kept verbatim for troubleshooting. Excluded from repr and
    # eq so PHI never leaks into logs/tracebacks (project rule) and a mutable dict
    # field doesn't break the frozen dataclass's generated equality.
    raw: Optional[Mapping[str, Any]] = field(default=None, repr=False, compare=False)
