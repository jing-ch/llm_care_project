"""
services.py — all business logic: DB operations, queue dispatch, helpers.
No HTTP request/response objects here.
"""

from django.db.models import Q

from .models import Provider, Patient, Order, CarePlan
from .tasks import generate_careplan_task


def _to_list(value):
    """Normalize a request value to a list for JSONField (may arrive as string or list)."""
    if value is None or value == '':
        return []
    if isinstance(value, list):
        return value
    return [str(value)]


def submit_careplan_request(data: dict) -> dict:
    """
    Orchestrate provider/patient/order/careplan creation and enqueue the Celery task.
    Returns a dict with care_plan_id and status.
    """
    provider, _ = Provider.objects.get_or_create(
        npi=data['referring_provider_npi'].strip(),
        defaults={'name': data['referring_provider'].strip() or 'Unknown'}
    )
    if provider.name != data['referring_provider'].strip():
        provider.name = data['referring_provider'].strip() or provider.name
        provider.save(update_fields=['name'])

    patient, _ = Patient.objects.get_or_create(
        mrn=data['patient_mrn'].strip(),
        defaults={
            'first_name': data['patient_first_name'].strip() or 'Unknown',
            'last_name': data['patient_last_name'].strip() or 'Unknown',
        }
    )
    patient.first_name = data['patient_first_name'].strip() or patient.first_name
    patient.last_name = data['patient_last_name'].strip() or patient.last_name
    patient.save(update_fields=['first_name', 'last_name'])

    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication_name=data['medication_name'].strip() or '',
        primary_diagnosis=data['primary_diagnosis'].strip() or '',
        additional_diagnoses=_to_list(data['additional_diagnoses']),
        medication_history=_to_list(data['medication_history']),
        patient_records=data['patient_records'] or '',
    )
    care_plan = CarePlan.objects.create(
        order=order,
        content='',
        status='pending',
    )

    generate_careplan_task.delay(care_plan.pk)

    return {'care_plan_id': care_plan.pk, 'status': 'pending'}


def get_careplan_by_id(care_plan_id: int):
    """Return a CarePlan by pk, or None if not found."""
    try:
        return CarePlan.objects.get(pk=care_plan_id)
    except CarePlan.DoesNotExist:
        return None


def search_careplans(q: str):
    """Return a queryset of CarePlans filtered by q (patient name or content)."""
    queryset = CarePlan.objects.select_related('order', 'order__patient').all()
    if q:
        queryset = queryset.filter(
            Q(order__patient__first_name__icontains=q) |
            Q(order__patient__last_name__icontains=q) |
            Q(content__icontains=q)
        )
    return queryset


def get_careplan_for_download(care_plan_id: int):
    """Return a CarePlan with related patient data pre-fetched, or None if not found."""
    try:
        return CarePlan.objects.select_related('order', 'order__patient').get(pk=care_plan_id)
    except CarePlan.DoesNotExist:
        return None


def build_download_filename(care_plan) -> str:
    """Build the .txt filename for the care plan download."""
    p = care_plan.order.patient
    name = f"{p.first_name}_{p.last_name}".strip() or 'careplan'
    return f"careplan_{care_plan.pk}_{name}.txt"
