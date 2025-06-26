# This is the single source of the Celery app for the project. Import celery_app from here in all worker modules.
import os
from celery import Celery

celery_app = Celery(
    "shushu_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    include=['src.worker.tasks']  # Auto-discover tasks
)

celery_app.conf.update(
    task_soft_time_limit=300,
    task_time_limit=600,
    result_expires=3600,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)