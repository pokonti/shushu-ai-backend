from fastapi import APIRouter
from src.worker.tasks import debug_add

router = APIRouter()

@router.get("/celery-test")
async def celery_test():
    # enqueue the task and return its ID
    task = debug_add.delay(4, 6)
    return {"task_id": task.id}
