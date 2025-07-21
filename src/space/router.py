from fastapi import APIRouter, HTTPException, Depends, Body, Query
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import get_current_user
from src.database import get_db
from src.media.models import Video, Audio
from src.space.service import create_resigned_upload_url
from src.worker.tasks import process_audio_task, process_video_task

router = APIRouter(tags=["Processing"])


@router.get("/generate-upload-url")
def generate_upload_url(filename: str, user: User = Depends(get_current_user)):
    """
    ENDPOINT 1: The frontend calls this first to get permission to upload.
    """
    if not filename.endswith((".mp4", ".mov", ".mkv", ".mp3", ".wav")):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    # Changed from create_signed_upload_url to create_presigned_upload_url
    url_data = create_resigned_upload_url(user_id=user.id, file_name=filename)
    if not url_data:
        raise HTTPException(status_code=500, detail="Could not create upload URL")
    return url_data


@router.post("/start-processing")
def start_processing(
        object_name: str = Body(..., embed=True),
        options: dict = Body(..., embed=True),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    """
    Starts a background processing job for an uploaded file.

    This endpoint is designed to be extremely fast. It does three things:
    1. Determines if the file is an audio or video file.
    2. Creates a new record in the appropriate database table with a 'PENDING' status.
       This record acts as the "job ticket".
    3. Dispatches the job to the correct Celery worker, passing the ID of the new record.
    4. Immediately returns the new 'job_id' to the frontend.
    """
    # Step 1: Determine the file type and corresponding database model.
    is_video = object_name.lower().endswith((".mp4", ".mov", ".mkv"))
    Model = Video if is_video else Audio

    # Step 2: Create the "job ticket" record in the database.
    # The 'status' field defaults to 'PENDING' as defined in your model.
    record = Model(
        user_id=user.id,
        file_path=object_name,  # Path to the original file in Spaces
        object_name=object_name,  # Store the object name as well
        status="PENDING",  # Explicitly set the initial status
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    print(f"Created new job record with ID: {record.id} for user {user.id}")

    # Step 3: Prepare arguments and dispatch the job to the correct Celery worker.
    task_args = {
        "job_id": record.id,
        "object_name": object_name,
        "options": options,
        "user_id": user.id
    }

    if is_video:
        print(f"Dispatching job {record.id} to video processing task...")
        process_video_task.delay(**task_args)
    else:
        print(f"Dispatching job {record.id} to audio processing task...")
        process_audio_task.delay(**task_args)

    # Step 4: Return the job ID immediately to the frontend.
    # The frontend will now use this ID to poll the /jobs/{job_id}/status endpoint.
    return {
        "message": "Processing has been successfully started.",
        "job_id": record.id
    }


@router.get("/jobs/{job_id}/status")
def get_job_status(
    job_id: int,
    media_type: str = Query(..., description="Specify 'audio' or 'video' to search the correct table.", enum=["video", "audio"]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Frontend calls this third, and repeatedly (polls), to check the job's progress.
    This endpoint is a simple, fast, read-only window into the database.
    """
    # 1. Determine which database table to query based on the media_type parameter.
    Model = Video if media_type == "video" else Audio

    # 2. Perform the database query.
    # It finds the record by its ID AND ensures it belongs to the logged-in user.
    record = db.query(Model).filter(Model.id == job_id, Model.user_id == user.id).first()

    # 3. Handle the case where the job doesn't exist or doesn't belong to the user.
    if not record:
        raise HTTPException(status_code=404, detail="Job not found or you do not have permission to view it.")

    # 4. Return the relevant information from the database record.
    # The frontend can use this data to update the UI.
    return {
        "job_id": record.id,
        "status": record.status,
        "public_url": record.public_url,
        "error": record.error_message
    }
