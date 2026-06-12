"""
intake/clinic_b.py — adapter for "Clinic B", a small clinic that posts orders as
JSON using its own field names. Worked example of source format -> InternalOrder.

Example Clinic B payload (note the field names differ from ours throughout):

    {
      "clinic": "Westside Family Clinic",
      "order_ref": "WFC-2024-00871",
      "patient": {
        "given": "Maria", "family": "Gonzalez",
        "record_number": "002145", "birthdate": "1980-07-22"
      },
      "ordering_md": {"full_name": "Dr. Alan Pierce", "npi_number": "1932087654"},
      "rx": {
        "drug_name": "Metformin 500mg",
        "diagnosis": "Type 2 Diabetes Mellitus",
        "other_dx": ["Hypertension", "Hyperlipidemia"],
        "prior_meds": ["Glipizide 5mg", "Lisinopril 10mg"]
      },
      "notes": "Patient reports occasional GI upset."
    }
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from careplan.errors import ValidationError
from careplan.internal_order import (
    InternalMedication,
    InternalOrder,
    InternalPatient,
    InternalProvider,
)

from .base import BaseIntakeAdapter

# Canonical format rules (same as serializers.NPI_RE / MRN_RE). Validation runs
# on the *converted* order, so every adapter checks against these same rules.
NPI_RE = re.compile(r'^\d{10}$')
MRN_RE = re.compile(r'^\d{6}$')


class ClinicBAdapter(BaseIntakeAdapter):
    source_name = "clinic_b"

    def parse(self, raw: Any) -> dict:
        """
        Accept Clinic B's payload as a JSON string/bytes or an already-decoded
        dict and return a plain dict. No renaming here — that's transform()'s job.
        """
        if isinstance(raw, (str, bytes, bytearray)):
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                raise ValidationError(
                    'Could not parse Clinic B payload as JSON.',
                    detail={'source': self.source_name},
                )
        else:
            data = raw

        if not isinstance(data, dict):
            raise ValidationError(
                'Clinic B payload must be a JSON object.',
                detail={'source': self.source_name},
            )
        return data

    def transform(self, parsed: dict) -> InternalOrder:
        """
        Map Clinic B's field names onto the canonical InternalOrder, and keep the
        original payload in `raw` so a failed order can be traced back to exactly
        what the clinic sent (under their own field names).
        """
        patient = parsed.get('patient') or {}
        provider = parsed.get('ordering_md') or {}
        rx = parsed.get('rx') or {}

        return InternalOrder(
            patient=InternalPatient(
                first_name=(patient.get('given') or '').strip(),
                last_name=(patient.get('family') or '').strip(),
                mrn=(patient.get('record_number') or '').strip(),
                date_of_birth=self._parse_dob(patient.get('birthdate')),
            ),
            provider=InternalProvider(
                name=(provider.get('full_name') or '').strip(),
                npi=(provider.get('npi_number') or '').strip(),
            ),
            medication=InternalMedication(
                name=(rx.get('drug_name') or '').strip(),
                primary_diagnosis=(rx.get('diagnosis') or '').strip(),
                additional_diagnoses=list(rx.get('other_dx') or []),
                medication_history=list(rx.get('prior_meds') or []),
            ),
            patient_records=(parsed.get('notes') or '').strip(),
            source=self.source_name,
            source_order_id=str(parsed.get('order_ref') or ''),
            raw=parsed,  # verbatim Clinic B payload, for troubleshooting
        )

    def validate(self, order: InternalOrder) -> None:
        """
        Check the canonical order against the shared format rules. Collects every
        problem and raises errors.ValidationError (-> 400) once. Duplicate /
        business rules are NOT here — services.py owns those.
        """
        problems: dict[str, str] = {}

        if not order.patient.first_name or not order.patient.last_name:
            problems['patient_name'] = 'Patient first and last name are required.'
        if not MRN_RE.match(order.patient.mrn):
            problems['mrn'] = 'MRN must be exactly 6 digits.'
        if not order.provider.name:
            problems['provider_name'] = 'Referring provider name is required.'
        if not NPI_RE.match(order.provider.npi):
            problems['npi'] = 'NPI must be exactly 10 digits.'
        if not order.medication.name:
            problems['medication_name'] = 'Medication name is required.'

        if problems:
            # Report source + source_order_id for traceability — never echo PHI
            # field values back in the error (project rule).
            raise ValidationError(
                'Clinic B order failed validation.',
                detail={
                    'source': order.source,
                    'source_order_id': order.source_order_id,
                    'fields': problems,
                },
            )

    @staticmethod
    def _parse_dob(value: Any) -> date | None:
        """Clinic B sends ISO dates ('1980-07-22'); tolerate missing/blank."""
        if not value:
            return None
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError:
            raise ValidationError(
                'Clinic B birthdate must be ISO format (YYYY-MM-DD).',
                detail={'source': 'clinic_b', 'field': 'patient.birthdate'},
            )
