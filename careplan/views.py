import json
import os

import redis
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from openai import OpenAI
from django.conf import settings

from .models import Provider, Patient, Order, CarePlan


redis_client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


def _to_list(value):
    """Normalize request value to a list for JSONField (API may send string or list)."""
    if value is None or value == '':
        return []
    if isinstance(value, list):
        return value
    return [str(value)]


def _call_llm(patient_first_name, patient_last_name, referring_provider, referring_provider_npi,
              patient_mrn, primary_diagnosis, medication_name, additional_diagnoses, medication_history, patient_records):
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    prompt = f"""You are a clinical pharmacist generating a care plan.

Required sections:
1. Problem list / Drug therapy problems
2. Goals (SMART)
3. Pharmacist interventions
4. Monitoring plan

Patient: {patient_first_name} {patient_last_name}, MRN: {patient_mrn}
Referring Provider: {referring_provider} (NPI: {referring_provider_npi})
Primary diagnosis: {primary_diagnosis}
Additional diagnoses: {additional_diagnoses or 'None'}
Medication: {medication_name}
Medication history: {medication_history or 'None'}
Patient records: {patient_records or 'None'}

Generate the care plan in plain text with the four sections clearly labeled."""

    r = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{'role': 'user', 'content': prompt}],
    )
    return r.choices[0].message.content


@require_GET
def home(request):
    return render(request, 'careplan/form.html')


@csrf_exempt
@require_POST
def generate_careplan(request):
    body = json.loads(request.body)
    patient_first_name = body.get('patient_first_name', '')
    patient_last_name = body.get('patient_last_name', '')
    referring_provider = body.get('referring_provider', '')
    referring_provider_npi = body.get('referring_provider_npi', '')
    patient_mrn = body.get('patient_mrn', '')
    primary_diagnosis = body.get('patient_primary_diagnosis', '')
    medication_name = body.get('medication_name', '')
    additional_diagnoses = body.get('additional_diagnoses', '')
    medication_history = body.get('medication_history', '')
    patient_records = body.get('patient_records', '')

    provider, _ = Provider.objects.get_or_create(
        npi=referring_provider_npi.strip(),
        defaults={'name': referring_provider.strip() or 'Unknown'}
    )
    if provider.name != referring_provider.strip():
        provider.name = referring_provider.strip() or provider.name
        provider.save(update_fields=['name'])

    patient, _ = Patient.objects.get_or_create(
        mrn=patient_mrn.strip(),
        defaults={
            'first_name': patient_first_name.strip() or 'Unknown',
            'last_name': patient_last_name.strip() or 'Unknown',
        }
    )
    patient.first_name = patient_first_name.strip() or patient.first_name
    patient.last_name = patient_last_name.strip() or patient.last_name
    patient.save(update_fields=['first_name', 'last_name'])

    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication_name=medication_name.strip() or '',
        primary_diagnosis=primary_diagnosis.strip() or '',
        additional_diagnoses=_to_list(additional_diagnoses),
        medication_history=_to_list(medication_history),
        patient_records=patient_records or '',
    )
    care_plan = CarePlan.objects.create(
        order=order,
        content='',
        status='pending',
    )
    care_plan_id = care_plan.pk

    try:
        redis_client.rpush("careplan_queue", care_plan_id)
    except redis.RedisError:
        return JsonResponse({'error': 'queue_unavailable'}, status=503)

    return JsonResponse(
        {
            'care_plan_id': care_plan_id,
            'status': 'pending',
        },
        status=202,
    )

def _care_plan_to_dict(care_plan):
    """Build API response dict from CarePlan instance (same shape as before)."""
    order = care_plan.order
    return {
        'id': care_plan.pk,
        'patient_first_name': order.patient.first_name,
        'patient_last_name': order.patient.last_name,
        'care_plan_text': care_plan.content,
    }


@require_GET
def get_careplan(request, care_plan_id):
    try:
        care_plan = CarePlan.objects.get(pk=care_plan_id)
    except CarePlan.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse(_care_plan_to_dict(care_plan))


@require_GET
def search_careplans(request):
    q = (request.GET.get('q') or '').strip().lower()
    queryset = CarePlan.objects.select_related('order', 'order__patient').all()
    if q:
        queryset = queryset.filter(
            Q(order__patient__first_name__icontains=q) |
            Q(order__patient__last_name__icontains=q) |
            Q(content__icontains=q)
        )
    results = [_care_plan_to_dict(cp) for cp in queryset]
    return JsonResponse({'results': results})


@require_GET
def download_careplan(request, care_plan_id):
    try:
        care_plan = CarePlan.objects.select_related('order', 'order__patient').get(pk=care_plan_id)
    except CarePlan.DoesNotExist:
        return JsonResponse({'error': 'not found'}, status=404)
    p = care_plan.order.patient
    name = f"{p.first_name}_{p.last_name}".strip() or 'careplan'
    filename = f"careplan_{care_plan_id}_{name}.txt"
    response = HttpResponse(care_plan.content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
