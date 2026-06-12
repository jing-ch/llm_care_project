"""
intake/base.py — every external source's adapter subclasses BaseIntakeAdapter.

The base class owns the pipeline ORDER (parse -> transform -> validate) through
the concrete `process()` template method; subclasses only fill in the three
steps. Business logic calls `adapter.process(raw)` and gets a validated
InternalOrder back — it never sees a source-specific format.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from careplan.internal_order import InternalOrder


class BaseIntakeAdapter(ABC):
    # Each subclass names its source, e.g. "react_frontend", "clinic_b".
    # Gets carried onto InternalOrder.source for provenance / dedup.
    source_name: str = ""

    @abstractmethod
    def parse(self, raw: Any) -> Any:
        """
        Decode the source's wire format (JSON / XML / HL7 / bytes) into a plain,
        source-shaped Python structure. No renaming, no business logic — just
        "make it readable". Raise on undecodable input.
        """
        raise NotImplementedError

    @abstractmethod
    def transform(self, parsed: Any) -> InternalOrder:
        """
        Map the source-shaped structure onto the canonical InternalOrder: rename
        fields, regroup into patient / provider / medication, set `source`. The
        only place that knows this source's field names.
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, order: InternalOrder) -> None:
        """
        Check the *canonical* order against shared rules (NPI 10 digits, MRN 6
        digits, required fields present). Raise errors.ValidationError on failure,
        return None on success. Duplicate / business-rule checks do NOT belong
        here — those stay in services.py.
        """
        raise NotImplementedError

    def process(self, raw: Any) -> InternalOrder:
        """
        Template method: the fixed pipeline every source runs through. Callers use
        this, never the three steps directly, so the order can't be gotten wrong
        and validate() can't be skipped.
        """
        parsed = self.parse(raw)
        order = self.transform(parsed)
        self.validate(order)
        return order
