import os
from celery import Celery
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

celery_app = Celery(
    "shushu_worker",
    broker=os.getenv("CELERY_BROKER_URL"),
    backend=os.getenv("CELERY_RESULT_BACKEND"),
    include=['src.worker.tasks']
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

# celery_app.conf.beat_schedule = {
#     # Give the schedule a name
#     'delete-old-files-every-hour': {
#         # Point it to the task by its name
#         'task': 'cleanup_old_files',
#         # Set the schedule. crontab(minute=0) runs at the top of every hour.
#         'schedule': crontab(minute=0),
#     },
# }