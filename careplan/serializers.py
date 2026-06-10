"""
serializers.py — data validation and format conversion (frontend ↔ backend).
No business logic here; just parsing input and shaping output.
"""

from rest_framework import serializers


class GenerateRequestSerializer(serializers.Serializer):
    """
    Validate and normalize the generate_careplan request body.

    All fields are optional here (no format rules yet — those arrive in Day 8).
    `validated_data` is shaped to match exactly what services.submit_careplan_request
    expects, including the frontend's `patient_primary_diagnosis` → `primary_diagnosis`
    rename (handled via `source`).
    """
    _text = dict(required=False, allow_blank=True, default='')

    patient_first_name = serializers.CharField(**_text)
    patient_last_name = serializers.CharField(**_text)
    referring_provider = serializers.CharField(**_text)
    referring_provider_npi = serializers.CharField(**_text)
    patient_mrn = serializers.CharField(**_text)
    patient_primary_diagnosis = serializers.CharField(source='primary_diagnosis', **_text)
    medication_name = serializers.CharField(**_text)
    additional_diagnoses = serializers.CharField(**_text)
    medication_history = serializers.CharField(**_text)
    patient_records = serializers.CharField(**_text)


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
