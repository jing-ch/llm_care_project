# Care Plan Auto-Generation System

Design Document

## 1. Overview

### 1.1 Background

A specialty pharmacy currently generates patient care plans manually by
pharmacists. Each care plan requires **20--40 minutes per patient**,
creating a significant operational bottleneck due to staffing shortages.

Care plans are required for: - Compliance - Medicare reimbursement -
Pharmaceutical manufacturer reporting

The goal of this system is to **automatically generate care plans**
using structured patient information and clinical records.

------------------------------------------------------------------------

### 1.2 Target Users

Internal healthcare workers (e.g., CVS pharmacists and medical
assistants).

Patients **do not interact with this system**.

Typical workflow:

1.  Medical assistant enters patient and order information.
2.  System validates the inputs.
3.  System calls an LLM to generate a **Care Plan**.
4.  Care plan is downloaded or printed for the patient.

------------------------------------------------------------------------

### 1.3 Key Constraints

-   **One Care Plan corresponds to one medication order**
-   Output must include:
    -   Problem list
    -   Goals
    -   Pharmacist interventions
    -   Monitoring plan

------------------------------------------------------------------------

# 2. System Goals

### Primary Goals

-   Reduce pharmacist time spent generating care plans.
-   Provide automated care plan generation using LLM.
-   Ensure compliance-ready documentation.

### Secondary Goals

-   Prevent duplicate patient/order submissions.
-   Maintain provider identity consistency.
-   Enable export for pharma reporting.

------------------------------------------------------------------------

# 3. Functional Requirements

## 3.1 Data Input

Medical assistants must input patient information through a **web
form**.

### Required Fields

  Field                       Type
  --------------------------- -----------------------
  Patient First Name          String
  Patient Last Name           String
  Referring Provider          String
  Referring Provider NPI      10-digit Number
  Patient MRN                 Unique 6-digit Number
  Patient Primary Diagnosis   ICD-10
  Medication Name             String
  Additional Diagnoses        List of ICD-10
  Medication History          List of strings
  Patient Records             Text or PDF

------------------------------------------------------------------------

## 3.2 Web Form Requirements

The UI must:

-   Validate all fields
-   Prevent invalid data
-   Provide duplicate warnings
-   Allow PDF upload for patient records

Validation examples:

  Field             Rule
  ----------------- -----------------------
  NPI               Must be 10 digits
  MRN               Must be unique
  ICD-10            Must match ICD format
  Medication list   Non-empty

------------------------------------------------------------------------

# 4. System Architecture (Python + Django)

### 4.1 High-Level Architecture

-   **Frontend**: Web client (React or Django Templates)
-   **Backend**: **Python + Django**
    -   Django REST Framework (DRF) provides API endpoints
    -   Django Admin for internal management
-   **Database**: PostgreSQL
-   **LLM Integration**:
    -   Django service layer prepares prompts and calls LLM API
-   **Storage**:
    -   Patient records stored as text or PDF

Architecture:

Web Client → Django REST API → Validation Layer → Duplicate Detection →
LLM Service → Database

------------------------------------------------------------------------

### 4.2 Django App Structure

Suggested modular structure:

    patients/
    providers/
    orders/
    careplans/
    common/

Descriptions:

-   **patients**: Patient model and lookup
-   **providers**: Provider registry with NPI uniqueness
-   **orders**: Medication orders and duplicate detection
-   **careplans**: Care plan generation and storage
-   **common**: Shared validation utilities

------------------------------------------------------------------------

# 5. Data Model

## 5.1 Patient

Fields:

-   MRN (Primary Key)
-   FirstName
-   LastName
-   DOB
-   Sex

------------------------------------------------------------------------

## 5.2 Provider

Fields:

-   NPI (Primary Key)
-   Name

Rules:

Provider must only exist once in the system.

------------------------------------------------------------------------

## 5.3 Medication Order

Fields:

-   OrderID (Primary Key)
-   MRN (Foreign Key)
-   MedicationName
-   PrimaryDiagnosis
-   AdditionalDiagnoses
-   ProviderNPI
-   CreatedDate

------------------------------------------------------------------------

## 5.4 Care Plan

Fields:

-   CarePlanID
-   OrderID
-   GeneratedText
-   CreatedAt

------------------------------------------------------------------------

# 6. Duplicate Detection Rules

  -----------------------------------------------------------------------
  Scenario                Action                  Reason
  ----------------------- ----------------------- -----------------------
  Same patient + same     ERROR (block            Definite duplicate
  medication + same day   submission)             

  Same patient + same     WARNING                 Possible refill
  medication + different                          
  day                                             

  Same MRN + different    WARNING                 Possible entry error
  name or DOB                                     

  Same name + DOB but     WARNING                 Possible same patient
  different MRN                                   

  Same NPI + different    ERROR                   NPI must be unique
  provider name                                   
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 7. LLM Care Plan Generation

## 7.1 Inputs to LLM

The model receives:

-   Patient demographics
-   Primary diagnosis
-   Secondary diagnoses
-   Medication
-   Medication history
-   Patient clinical records

------------------------------------------------------------------------

## 7.2 Prompt Template

Example prompt:

You are a clinical pharmacist generating a care plan.

Required sections:

1.  Problem list / Drug therapy problems
2.  Goals (SMART)
3.  Pharmacist interventions
4.  Monitoring plan

------------------------------------------------------------------------

## 7.3 Output Structure

### Problem List

Drug therapy problems and risks.

### Goals (SMART)

Treatment outcomes and safety objectives.

### Pharmacist Interventions

-   Dosing
-   Premedication
-   Infusion instructions
-   Adverse event management

### Monitoring Plan

-   Lab schedule
-   Vital monitoring
-   Follow-up checks

------------------------------------------------------------------------

# 8. Reporting & Export

## 8.1 MVP: CSV Export

Initial version supports **CSV export only** for reporting to
pharmaceutical partners.

Suggested CSV fields:

-   care_plan_id
-   order_id
-   patient_mrn
-   patient_first_name
-   patient_last_name
-   provider_npi
-   provider_name
-   primary_diagnosis_icd10
-   additional_diagnoses_icd10
-   medication_name
-   created_at
-   care_plan_text

------------------------------------------------------------------------

## 8.2 Future Considerations

Future enhancements may include:

-   JSON export
-   PDF export
-   Pharma-specific templates
-   Scheduled automated export
-   Secure delivery integrations

------------------------------------------------------------------------

# 9. Error Handling

Errors must be:

-   Safe
-   Clear
-   Contained

Examples:

  Case              System Response
  ----------------- -------------------------------
  Duplicate order   Block submission
  Invalid NPI       Validation error
  LLM failure       Retry or return error message

------------------------------------------------------------------------

# 10. Production Requirements

The system must meet production-ready standards.

### Validation

All inputs must be validated.

### Data Integrity

Business rules enforced using database constraints and application
logic.

### Error Safety

Failures should not corrupt existing data.

### Code Quality

-   Modular structure
-   Readable and maintainable code

### Testing

Automated tests should cover:

-   Validation rules
-   Duplicate detection
-   Care plan generation pipeline

### Deployment

The system should run **end-to-end out of the box**.

------------------------------------------------------------------------

# 11. Example Input

Name: A.B. MRN: 00012345 DOB: 1979-06-08 Sex: Female

Primary diagnosis: Generalized myasthenia gravis

Medication: IVIG

------------------------------------------------------------------------

# 12. Example Output (Care Plan)

Problem list - Need for rapid immunomodulation - Risk of infusion
reactions - Risk of renal dysfunction

Goals - Improve muscle strength within 2 weeks - Avoid infusion
reactions

Pharmacist interventions - IVIG dosing plan - Premedication protocol -
Infusion monitoring

Monitoring plan - CBC and BMP baseline - Vital signs during infusion -
Post-treatment renal function check
