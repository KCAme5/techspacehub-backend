import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybercraft.settings')

app = Celery('cybercraft')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Explicitly ensure broker and backend are set from settings if they aren't already
# This acts as a fallback if config_from_object has issues
if not app.conf.broker_url or '127.0.0.1' in app.conf.broker_url or 'localhost' in app.conf.broker_url:
    if hasattr(settings, 'CELERY_BROKER_URL'):
        app.conf.broker_url = settings.CELERY_BROKER_URL
    if hasattr(settings, 'CELERY_RESULT_BACKEND'):
        app.conf.result_backend = settings.CELERY_RESULT_BACKEND

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
