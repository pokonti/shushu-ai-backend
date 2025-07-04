from fastapi import APIRouter, HTTPException, Depends, Body, Query
from sqlalchemy.orm import Session
from tempfile import TemporaryDirectory
import os
import httpx

from src.auth.models import User
from src.auth.service import get_current_user
from src.database import get_db
from src.media.models import Video, Audio
from src.space.service import create_resigned_upload_url, download_file_from_space
from src.media.service import extract_audio_from_video, replace_audio_in_video
from src.preprocessing.denoiser import process_audio_from_url
from src.space.service import upload_processed_file_to_space
from src.preprocessing.filler import remove_filler_words_from_audio, \
    get_filler_timestamps_from_audio, remove_filler_words_smooth
from src.summary.service import get_summary
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


@router.post("/process-audio")
async def process_audio(
        object_name: str = Body(..., embed=True),
        options: dict = Body(..., embed=True),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    """
    Processes a pure audio file based on user-selected options.
    This function now has a flexible pipeline.
    """
    with TemporaryDirectory() as temp_dir:
        # --- Stage 1: Initial Setup ---
        # Download the original file from Spaces. This is our starting point.
        local_original_path = os.path.join(temp_dir, os.path.basename(object_name))
        download_file_from_space(object_name, local_original_path)

        # This variable will hold the path to the most recently processed version of the file.
        current_file_path = local_original_path

        # --- Stage 2: Conditional Denoising (Cleanvoice) ---
        if options.get("denoise"):
            print("Denoise option selected. Processing with Cleanvoice...")
            # To process with Cleanvoice, we need a public URL of the ORIGINAL file.
            original_public_url = f"https://{os.getenv('DO_SPACES_BUCKET_NAME')}.{os.getenv('DO_SPACES_REGION')}.cdn.digitaloceanspaces.com/{object_name}"

            processed_audio_url = await process_audio_from_url(original_public_url, options)

            # Download the result from Cleanvoice. This becomes our new "current" file.
            denoised_local_path = os.path.join(temp_dir, "audio_denoised.wav")
            async with httpx.AsyncClient() as client:
                response = await client.get(processed_audio_url)
                with open(denoised_local_path, 'wb') as f:
                    f.write(response.content)

            current_file_path = denoised_local_path  # CRUCIAL: Update the working path
            print(f"Denoising complete. New working file: {current_file_path}")

        # --- Stage 3: Conditional Filler Word Removal (Local) ---
        if options.get("removeFillers"):
            print(f"Remove Fillers option selected. Processing file: {current_file_path}...")
            # This function runs on the output of the previous step.
            cleaned_local_path = remove_filler_words_from_audio(current_file_path)

            current_file_path = cleaned_local_path  # CRUCIAL: Update the working path again
            print(f"Filler word removal complete. New working file: {current_file_path}")
        else:
            print("Remove Fillers option not selected. Skipping.")

        # --- Stage 4: Conditional Summarization (Local) ---
        summary_text = None
        if options.get("summarize"):
            print(f"Summarize option selected. Analyzing file: {current_file_path}...")
            # Summarization runs on the final version of the audio.
            summary_text = get_summary(current_file_path)  # Assumes this function exists
            print("Summarization complete.")
        else:
            print("Summarize option not selected. Skipping.")

        # --- Stage 5: Final Upload ---
        # Upload the final version of the file, whatever it may be.
        print(f"Uploading final processed file '{current_file_path}' to Spaces...")
        processed_object_name = object_name.replace("originals/", "processed/")
        final_upload_info = upload_processed_file_to_space(current_file_path, processed_object_name)

    # --- Stage 6: Save to Database ---
    record = Audio(
        user_id=user.id,
        file_path=final_upload_info["public_url"],
        object_name=final_upload_info["spaces_uri"],
        public_url=final_upload_info["public_url"],
        summary=summary_text  # Save the summary to the DB
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "Processing complete!",
        "public_url": record.public_url,
        "summary": record.summary
    }

@router.post("/process-video")
async def process_video(
        object_name: str = Body(..., embed=True),
        options: dict = Body(..., embed=True),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    """
    Processes a video file based on user-selected options for its audio track.
    Workflow: Download Video -> Extract Audio -> [Conditional Audio Processing Pipeline] ->
              Recombine Audio/Video -> Upload Final Video -> Save DB.
    """
    with TemporaryDirectory() as temp_dir:
        # --- Stage 1: Initial Setup ---
        # 1. Download the original video file from Spaces.
        original_video_local_path = os.path.join(temp_dir, os.path.basename(object_name))
        print(f"Downloading original video: {object_name}...")
        download_file_from_space(object_name, original_video_local_path)

        # 2. Extract the audio track from the video.
        print("Extracting audio from video...")
        extracted_audio_local_path = extract_audio_from_video(original_video_local_path)

        # This variable will track the latest version of the audio file through the pipeline.
        current_audio_path = extracted_audio_local_path
        current_video_path = original_video_local_path

        # --- Stage 2: Conditional Denoising on the Extracted Audio ---
        if options.get("denoise"):
            print("Denoise option selected. Processing extracted audio with Cleanvoice...")

            # To use Cleanvoice, the extracted audio needs its own temporary public URL.
            temp_audio_object_name = f"users/{user.id}/temp/{os.path.basename(extracted_audio_local_path)}"
            temp_audio_info = upload_processed_file_to_space(extracted_audio_local_path, temp_audio_object_name)

            # Call Cleanvoice with the temporary URL.
            processed_audio_url = await process_audio_from_url(temp_audio_info['public_url'], options)

            # Download the result from Cleanvoice. This becomes our new working audio file.
            denoised_local_path = os.path.join(temp_dir, "audio_denoised.wav")
            async with httpx.AsyncClient() as client:
                response = await client.get(processed_audio_url)
                with open(denoised_local_path, 'wb') as f:
                    f.write(response.content)

            current_audio_path = denoised_local_path
            current_video_path = replace_audio_in_video(original_video_local_path, current_audio_path, temp_dir)
            print(f"Denoising complete. New working audio: {current_audio_path}")

        # --- Stage 3: Conditional Filler Word Removal ---
        if options.get("removeFillers"):
            print(f"Remove Fillers option selected. Processing audio: {current_audio_path}...")

            filler_times = get_filler_timestamps_from_audio(current_audio_path)
            # current_audio_path = remove_filler_words_from_audio(current_audio_path, filler_times)
            #
            # current_video_path = remove_filler_words_smooth(current_video_path, filler_times)

            current_video_path = remove_filler_words_smooth(current_video_path, filler_times)
            current_audio_path = extract_audio_from_video(current_video_path)



            print(f"Filler word removal complete. New working audio: {current_audio_path}")
        else:
            print("Remove Fillers option not selected. Skipping.")

        # --- Stage 4: Conditional Summarization ---
        summary_text = None
        if options.get("summarize"):
            print(f"Summarize option selected. Analyzing audio: {current_audio_path}...")
            # Summarization runs on the final version of the audio.
            summary_text = get_summary(current_audio_path)
            print("Summarization complete.")
        else:
            print("Summarize option not selected. Skipping.")

        # --- Stage 5: Recombine and Final Upload ---
        # Recombine the final processed audio with the original video.
        print(f"Recombining final audio ('{os.path.basename(current_audio_path)}') with original video...")
        final_video_local_path = replace_audio_in_video(current_video_path, current_audio_path, temp_dir)
        # Upload the final video file to Spaces.
        print(f"Uploading final processed video '{os.path.basename(final_video_local_path)}' to Spaces...")
        processed_object_name = object_name.replace("originals/", "processed/")
        final_upload_info = upload_processed_file_to_space(final_video_local_path, processed_object_name)

    # --- Stage 6: Save to Database ---
    record = Video(
        user_id=user.id,
        file_path=final_upload_info["public_url"],
        object_name=final_upload_info["spaces_uri"],
        public_url=final_upload_info["public_url"],
        summary=summary_text
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "Video processing complete!",
        "public_url": record.public_url,
        "summary": record.summary
    }


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
        "status": record.status,           # e.g., "PENDING", "PROCESSING", "COMPLETED", "FAILED"
        "public_url": record.public_url, # Will be null until the job is 'COMPLETED'
        "summary": record.summary,         # Will be null until the job is 'COMPLETED'
        "error": record.error_message    # Will be populated if the status is 'FAILED'
    }
