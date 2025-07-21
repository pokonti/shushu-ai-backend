from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from src.auth.models import User
from src.auth.service import get_current_user
from src.database import get_db
from src.media.models import Video
from src.space.service import create_resigned_upload_url
from src.worker.tasks import start_shorts_analysis_task

router = APIRouter(tags=["Shorts"])
@router.get("/shorts/generate-upload-url")
def generate_shorts_upload_url(filename: str, user: User = Depends(get_current_user)):
    """
    Step 1 — Get a pre-signed upload URL for a Shorts video file.
    """
    if not filename.lower().endswith((".mp4", ".mov", ".mkv",'.avi', '.webm', ".HEVC", ".MP4", ".MOV", ".MKV")):
        raise HTTPException(status_code=400, detail="Unsupported format for Shorts")

    url_data = create_resigned_upload_url(user_id=user.id, file_name=filename)
    if not url_data:
        raise HTTPException(status_code=500, detail="Could not create upload URL")

    return url_data


@router.post("/shorts/start-processing")
def start_shorts_processing(
    object_name: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Step 2 — Create a Shorts job and dispatch Celery task.
    """
    record = Video(
        user_id=user.id,
        object_name=object_name,
        file_path=object_name,
        status="PENDING"
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # task_args = {
    #     "job_id": record.id,
    #     "object_name": object_name,
    #     "user_id": user.id
    # }
    start_shorts_analysis_task.delay(
        job_id=record.id,
        object_name=object_name,
        user_id=user.id
    )

    # process_shorts_task.delay(**task_args)

    return {
        "message": "Shorts processing started.",
        "job_id": record.id
    }