import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careplan_project.settings")

app = Celery("careplan_project")

# Read broker/backend URL and task config from Django settings (CELERY_* keys)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every INSTALLED_APP
app.autodiscover_tasks()
