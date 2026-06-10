"""
services.py — all business logic: DB operations, queue dispatch, helpers.
No HTTP request/response objects here.
"""

from django.db.models import Q
from django.utils import timezone

from .models import Provider, Patient, Order, CarePlan
from .tasks import generate_careplan_task
from . import errors


def _to_list(value):
    """Normalize a request value to a list for JSONField (may arrive as string or list)."""
    if value is None or value == '':
        return []
    if isinstance(value, list):
        return value
    return [str(value)]


def submit_careplan_request(data: dict) -> dict:
    """
    Run the business rules, then (if clear) create provider/patient/order/careplan
    and enqueue the Celery task. Returns {'care_plan_id', 'status'}.

    Business rules (see CLAUDE.md):
      Provider  same NPI + different name           -> BlockError (409)
      Patient   same MRN + different name or DOB     -> warning
      Patient   same name + DOB + different MRN      -> warning
      Order     same patient + same med + same day   -> BlockError (409)
      Order     same patient + same med + other day  -> warning

    Blocks raise immediately. Warnings are collected and, unless the caller has
    set acknowledge_warnings, raised together as a WarningException (HTTP 200) so
    the user can confirm and resubmit. Nothing is written until all checks pass.
    """
    acknowledge = data.get('acknowledge_warnings', False)
    warnings = []

    npi = data['referring_provider_npi'].strip()
    provider_name = data['referring_provider'].strip()
    mrn = data['patient_mrn'].strip()
    first = data['patient_first_name'].strip()
    last = data['patient_last_name'].strip()
    dob = data.get('date_of_birth')
    medication = data['medication_name'].strip()

    # --- Provider: same NPI + different name = BLOCK; same name = reuse ---
    provider = Provider.objects.filter(npi=npi).first()
    if provider and provider_name and provider.name != provider_name:
        raise errors.BlockError(
            'A provider with this NPI already exists under a different name.',
            code='PROVIDER_NAME_CONFLICT',
            detail={'npi': npi, 'existing_name': provider.name, 'submitted_name': provider_name},
        )

    # --- Patient: name/DOB mismatch on a known MRN, or a twin under another MRN ---
    patient = Patient.objects.filter(mrn=mrn).first()
    if patient:
        if (first or last) and (patient.first_name, patient.last_name) != (first, last):
            warnings.append({
                'code': 'PATIENT_NAME_MISMATCH',
                'message': f'MRN {mrn} is already on file under a different name '
                           f'({patient.first_name} {patient.last_name}).',
            })
        if dob and patient.date_of_birth and patient.date_of_birth != dob:
            warnings.append({
                'code': 'PATIENT_DOB_MISMATCH',
                'message': f'MRN {mrn} is already on file with a different date of birth.',
            })
    if first and last and dob:
        twin = (Patient.objects
                .filter(first_name=first, last_name=last, date_of_birth=dob)
                .exclude(mrn=mrn).first())
        if twin:
            warnings.append({
                'code': 'PATIENT_MRN_MISMATCH',
                'message': f'A patient with the same name and date of birth already '
                           f'exists under MRN {twin.mrn}.',
            })

    # --- Order: same patient + same medication, same day = BLOCK, other day = warning ---
    if patient and medication:
        same_med = Order.objects.filter(patient=patient, medication_name=medication)
        today = timezone.now().date()
        if same_med.filter(created_at__date=today).exists():
            raise errors.BlockError(
                'An order for this patient and medication already exists today.',
                code='DUPLICATE_ORDER_TODAY',
                detail={'mrn': mrn, 'medication': medication},
            )
        if same_med.exists():
            warnings.append({
                'code': 'DUPLICATE_ORDER_OTHER_DAY',
                'message': f'This patient already has an order for {medication} on another day.',
            })

    # --- Gate: hold for confirmation unless the user already acknowledged ---
    if warnings and not acknowledge:
        raise errors.WarningException(
            'Please review the following before continuing.',
            code='REVIEW_REQUIRED',
            detail={'warnings': warnings},
        )

    # --- All clear: create/reuse and enqueue ---
    if provider is None:
        provider = Provider.objects.create(npi=npi, name=provider_name or 'Unknown')
    if patient is None:
        patient = Patient.objects.create(
            mrn=mrn,
            first_name=first or 'Unknown',
            last_name=last or 'Unknown',
            date_of_birth=dob,
        )

    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication_name=medication,
        primary_diagnosis=data['primary_diagnosis'].strip(),
        additional_diagnoses=_to_list(data['additional_diagnoses']),
        medication_history=_to_list(data['medication_history']),
        patient_records=data['patient_records'] or '',
    )
    care_plan = CarePlan.objects.create(order=order, content='', status='pending')

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
