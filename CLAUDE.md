## Project: CarePlan Generation System

### What this project does
A web system for CVS pharmacy workers to generate medical care plans.
A medical assistant inputs patient info → system calls an LLM → generates a care plan document they can download.

### Tech stack
- Backend: Python, Django, Django REST Framework
- Frontend: React
- Database: PostgreSQL
- Async tasks (local): Celery + Redis
- AI/LLM: Claude API or OpenAI API
- Containerization: Docker + Docker Compose
- Cloud: AWS (Lambda, SQS, RDS, API Gateway)
- Infrastructure: Terraform
- Monitoring: Prometheus + Grafana
- Testing: pytest

### Architecture (added gradually over the course)
- views.py → only handles HTTP requests and responses
- serializers.py → data validation and format conversion
- services.py → all business logic (LLM calls, queue, database)
- models.py → database table definitions
- tasks.py → Celery async tasks

### Business rules (important, never skip these)
- One care plan per order (one medication)
- Care plan must contain: Problem list, Goals, Pharmacist interventions, Monitoring plan
- NPI must be exactly 10 digits
- MRN must be exactly 6 digits
- Provider: same NPI + different name = ERROR (block)
- Provider: same NPI + same name = reuse existing
- Patient: same MRN + different name or DOB = WARNING (user can confirm and continue)
- Patient: same name + DOB + different MRN = WARNING
- Order: same patient + same medication + same day = ERROR (block)
- Order: same patient + same medication + different day = WARNING (user can confirm and continue)

### How we build this
We build incrementally, one day at a time. Do NOT add features that haven't been introduced yet.
- Day 2: sync MVP only, no validation, no async
- Day 3: add database models
- Day 4: add Redis queue (but no worker yet)
- Day 5: add Celery worker
- Day 6: add polling for frontend updates
- Day 7: refactor into views/serializers/services
- Day 8: add validation, duplicate detection, tests
...and so on

### Critical constraints
- Never expose stack traces or PHI (patient health info) in API error responses
- LLM calls must have error handling, never crash the app
- Project must run end-to-end with docker-compose up
- Always use environment variables for secrets (API keys, DB passwords)
- Never hardcode credentials in code
