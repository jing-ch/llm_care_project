import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from openai import OpenAI
from django.conf import settings

# In-memory store: id -> { ... }
care_plans_store = {}
_next_id = 1


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

    care_plan_text = _call_llm(
        patient_first_name, patient_last_name, referring_provider, referring_provider_npi,
        patient_mrn, primary_diagnosis, medication_name, additional_diagnoses, medication_history, patient_records
    )

    global _next_id
    care_plan_id = _next_id
    _next_id += 1
    care_plans_store[care_plan_id] = {
        'id': care_plan_id,
        'patient_first_name': patient_first_name,
        'patient_last_name': patient_last_name,
        'care_plan_text': care_plan_text,
    }

    return JsonResponse({
        'care_plan_id': care_plan_id,
        'care_plan_text': care_plan_text,
    })

@require_GET
def get_careplan(request, care_plan_id):
    care_plan = care_plans_store.get(care_plan_id)
    if care_plan is None:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse(care_plan)


@require_GET
def search_careplans(request):
    q = (request.GET.get('q') or '').strip().lower()
    if not q:
        results = list(care_plans_store.values())
    else:
        results = []
        for cp in care_plans_store.values():
            if (q in (cp.get('patient_first_name') or '').lower() or
                q in (cp.get('patient_last_name') or '').lower() or
                q in (cp.get('care_plan_text') or '').lower()):
                results.append(cp)
    return JsonResponse({'results': results})


@require_GET
def download_careplan(request, care_plan_id):
    care_plan = care_plans_store.get(care_plan_id)
    if care_plan is None:
        return JsonResponse({'error': 'not found'}, status=404)
    name = f"{care_plan.get('patient_first_name', '')}_{care_plan.get('patient_last_name', '')}".strip() or 'careplan'
    filename = f"careplan_{care_plan_id}_{name}.txt"
    content = care_plan.get('care_plan_text', '')
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
