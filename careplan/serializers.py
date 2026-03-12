"""
serializers.py — data validation and format conversion (frontend ↔ backend).
No business logic here; just parsing input and shaping output.
"""


def parse_generate_request(body: dict) -> dict:
    """Extract and normalize fields from the generate_careplan request body."""
    return {
        'patient_first_name': body.get('patient_first_name', ''),
        'patient_last_name': body.get('patient_last_name', ''),
        'referring_provider': body.get('referring_provider', ''),
        'referring_provider_npi': body.get('referring_provider_npi', ''),
        'patient_mrn': body.get('patient_mrn', ''),
        'primary_diagnosis': body.get('patient_primary_diagnosis', ''),
        'medication_name': body.get('medication_name', ''),
        'additional_diagnoses': body.get('additional_diagnoses', ''),
        'medication_history': body.get('medication_history', ''),
        'patient_records': body.get('patient_records', ''),
    }


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
