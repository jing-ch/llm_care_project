"""
serializers.py — data validation and format conversion (frontend ↔ backend).
No business logic here; just parsing input and shaping output.
"""

import re

from rest_framework import serializers

NPI_RE = re.compile(r'^\d{10}$')
MRN_RE = re.compile(r'^\d{6}$')


class GenerateRequestSerializer(serializers.Serializer):
    """
    Validate and normalize the generate_careplan request body.

    `validated_data` is shaped to match exactly what services.submit_careplan_request
    expects, including the frontend's `patient_primary_diagnosis` → `primary_diagnosis`
    rename (handled via `source`).

    Format rules (NPI / MRN) live here as field validators; they raise DRF's
    ValidationError, which careplan.errors normalizes into the 400 envelope.
    Duplicate/business rules live in services.py (block/warning).
    """
    _text = dict(required=False, allow_blank=True, default='')

    patient_first_name = serializers.CharField(**_text)
    patient_last_name = serializers.CharField(**_text)
    referring_provider = serializers.CharField(**_text)
    referring_provider_npi = serializers.CharField()   # required + format-checked
    patient_mrn = serializers.CharField()              # required + format-checked
    patient_primary_diagnosis = serializers.CharField(source='primary_diagnosis', **_text)
    medication_name = serializers.CharField(**_text)
    additional_diagnoses = serializers.CharField(**_text)
    medication_history = serializers.CharField(**_text)
    patient_records = serializers.CharField(**_text)
    # Optional: enables the DOB-based duplicate rules when the frontend sends it.
    date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    # Set true on resubmit to proceed past warnings the user has acknowledged.
    acknowledge_warnings = serializers.BooleanField(required=False, default=False)

    def validate_referring_provider_npi(self, value):
        value = value.strip()
        if not NPI_RE.match(value):
            raise serializers.ValidationError('NPI must be exactly 10 digits.')
        return value

    def validate_patient_mrn(self, value):
        value = value.strip()
        if not MRN_RE.match(value):
            raise serializers.ValidationError('MRN must be exactly 6 digits.')
        return value


def serialize_careplan(care_plan) -> dict:
    """Build API response dict from a CarePlan instance."""
    order = care_plan.order
    return {
        'id': care_plan.pk,
        'patient_first_name': order.patient.first_name,
        'patient_last_name': order.patient.last_name,
        'care_plan_text': care_plan.content,
    }


def serialize_careplan_status(care_plan) -> dict:
    """Build status-check response dict from a CarePlan instance."""
    response = {
        'id': care_plan.pk,
        'status': care_plan.status,
    }
    if care_plan.status == 'completed':
        response['content'] = care_plan.content
    return response
