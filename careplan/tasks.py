import os
import time

from celery import shared_task
from django.conf import settings
from openai import OpenAI

from .models import CarePlan

MOCK_CAREPLAN = """
CARE PLAN (MOCK)
================

1. Problem List / Drug Therapy Problems
   - [MOCK] Hypertension, uncontrolled
   - [MOCK] Potential drug-drug interaction identified

2. Goals (SMART)
   - Blood pressure < 130/80 mmHg within 4 weeks
   - Patient education on medication adherence completed by next visit

3. Pharmacist Interventions
   - [MOCK] Reviewed current medication regimen
   - [MOCK] Counseled patient on proper administration
   - [MOCK] Recommended follow-up with prescriber

4. Monitoring Plan
   - [MOCK] Blood pressure check in 2 weeks
   - [MOCK] Labs (BMP) in 4 weeks
   - [MOCK] Reassess therapy at 3-month follow-up
""".strip()


def _call_llm(prompt: str) -> str:
    """Call the LLM. Swaps in a mock when USE_MOCK_LLM=true."""
    if os.environ.get("USE_MOCK_LLM", "").lower() == "true":
        time.sleep(1)  # simulate network latency
        return MOCK_CAREPLAN

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _build_prompt(order):
    patient = order.patient
    provider = order.provider
    return f"""You are a clinical pharmacist generating a care plan.

Required sections:
1. Problem list / Drug therapy problems
2. Goals (SMART)
3. Pharmacist interventions
4. Monitoring plan

Patient: {patient.first_name} {patient.last_name}, MRN: {patient.mrn}
Referring Provider: {provider.name} (NPI: {provider.npi})
Primary diagnosis: {order.primary_diagnosis}
Additional diagnoses: {order.additional_diagnoses or 'None'}
Medication: {order.medication_name}
Medication history: {order.medication_history or 'None'}
Patient records: {order.patient_records or 'None'}

Generate the care plan in plain text with the four sections clearly labeled."""


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=2,  # overridden below with exponential back-off
)
def generate_careplan_task(self, care_plan_id: int):
    """
    Pull order data from DB, call LLM, save result.
    Retries up to 3 times with exponential back-off: 2s → 4s → 8s.
    """
    try:
        care_plan = CarePlan.objects.select_related(
            "order", "order__patient", "order__provider"
        ).get(pk=care_plan_id)
    except CarePlan.DoesNotExist:
        # Nothing to retry — the record is gone.
        return

    care_plan.status = "processing"
    care_plan.save(update_fields=["status", "updated_at"])

    try:
        prompt = _build_prompt(care_plan.order)
        content = _call_llm(prompt)

        care_plan.content = content
        care_plan.status = "completed"
        care_plan.save(update_fields=["content", "status", "updated_at"])

    except Exception as exc:
        retry_number = self.request.retries          # 0, 1, 2
        countdown = 2 ** (retry_number + 1)          # 2s, 4s, 8s

        if self.request.retries < self.max_retries:
            care_plan.status = "pending"
            care_plan.save(update_fields=["status", "updated_at"])
            raise self.retry(exc=exc, countdown=countdown)
        else:
            # All retries exhausted
            care_plan.status = "failed"
            care_plan.save(update_fields=["status", "updated_at"])
            raise
