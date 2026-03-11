from celery import shared_task
from django.conf import settings
from openai import OpenAI

from .models import CarePlan


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
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = _build_prompt(care_plan.order)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content

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
