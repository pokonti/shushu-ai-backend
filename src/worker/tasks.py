import datetime
import os
from celery import current_task

from src.auth.models import User
from src.database import SessionLocal
from src.media.models import Audio, Video
from src.media.service import extract_audio_from_video, replace_audio_in_video
from src.preprocessing.denoiser import process_audio_from_url
from src.preprocessing.filler import remove_filler_words_from_audio, get_filler_timestamps_from_audio, \
    remove_filler_words_smooth
from src.space.service import upload_processed_file_to_space, download_file_from_space, delete_file_from_space
from src.summary.service import get_summary
from src.worker.celery_app import celery_app
import httpx
from tempfile import TemporaryDirectory
import asyncio


@celery_app.task(bind=True)
def debug_add(self, x: int, y: int) -> int:
    """Simple test task"""
    return x + y


async def _process_audio_async(job_id: int, object_name: str, options: dict, user_id: int):
    """
    This is the core async logic. It is NOT a celery task itself.
    It contains all the await calls.
    """
    db = SessionLocal()
    record = db.query(Audio).filter(Audio.id == job_id).first()
    if not record:
        return {"status": "FAILED", "error": "Job record not found."}

    try:
        record.status = "PROCESSING"
        db.commit()

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

        record.status = "COMPLETED"
        record.public_url = final_upload_info["public_url"]
        record.file_path = final_upload_info["public_url"]
        record.summary = summary_text
        db.commit()
        return {"status": "COMPLETED", "public_url": record.public_url}

    except Exception as e:
        record.status = "FAILED"
        record.error_message = str(e)
        db.commit()
        raise e
    finally:
        db.close()


# --- Main async logic for video processing ---
async def _process_video_async(job_id: int, object_name: str, options: dict, user_id: int):
    """Core async logic for video processing."""
    db = SessionLocal()
    record = db.query(Video).filter(Video.id == job_id).first()
    user_id = db.query(User).filter(User.id == user_id).first()
    if not record:
        return {"status": "FAILED", "error": "Job record not found."}

    try:
        record.status = "PROCESSING"
        db.commit()

        # --- The entire CORRECT video pipeline we designed before goes here ---
        # It can now use 'await' for things like the Cleanvoice call.
        with TemporaryDirectory() as temp_dir:
            # --- Stage 1: Initial Setup ---
            # 1. Download the original video file from Spaces.
            original_video_local_path = os.path.join(temp_dir, os.path.basename(object_name))
            print(f"Downloading original video: {object_name}...")
            download_file_from_space(object_name, original_video_local_path)

            # 2. Extract the audio track from the video.
            print("Extracting audio from video...")
            # The 'temp_dir' is passed as the output directory.
            extracted_audio_path = extract_audio_from_video(
                video_path_str=original_video_local_path,
                output_dir_str=temp_dir
            )

            # This variable will track the latest version of the audio file through the pipeline.
            current_audio_path = extracted_audio_path
            current_video_path = original_video_local_path

            # --- Stage 2: Conditional Denoising on the Extracted Audio ---
            if options.get("denoise"):
                print("Denoise option selected. Processing extracted audio with Cleanvoice...")

                # To use Cleanvoice, the extracted audio needs its own temporary public URL.
                temp_audio_object_name = f"users/{user_id}/temp/{os.path.basename(extracted_audio_path)}"
                temp_audio_info = upload_processed_file_to_space(extracted_audio_path, temp_audio_object_name)

                # Call Cleanvoice with the temporary URL.
                processed_audio_url = await process_audio_from_url(temp_audio_info['public_url'], options)

                # Download the result from Cleanvoice. This becomes our new working audio file.
                denoised_local_path = os.path.join(temp_dir, "audio_denoised.wav")
                async with httpx.AsyncClient() as client:
                    response = await client.get(processed_audio_url)
                    with open(denoised_local_path, 'wb') as f:
                        f.write(response.content)

                current_audio_path = denoised_local_path
                current_video_path = replace_audio_in_video(
                    video_path_str=original_video_local_path,
                    new_audio_path_str=current_audio_path,
                    output_dir_str=temp_dir
                )
                print(f"Denoising complete. New working audio: {current_audio_path}")

            # --- Stage 3: Conditional Filler Word Removal ---
            if options.get("removeFillers"):
                print(f"Remove Fillers option selected. Processing audio: {current_audio_path}...")

                filler_times = get_filler_timestamps_from_audio(current_audio_path)

                current_video_path = remove_filler_words_smooth(current_video_path, filler_times)

                current_audio_path = extract_audio_from_video(
                    video_path_str=current_video_path,
                    output_dir_str=temp_dir
                )

                print(f"Filler word removal complete. New working audio: {current_audio_path}")

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
            final_video_local_path = replace_audio_in_video(current_video_path, current_audio_path)
            # Upload the final video file to Spaces.
            print(f"Uploading final processed video '{os.path.basename(final_video_local_path)}' to Spaces...")
            processed_object_name = object_name.replace("originals/", "processed/")
            final_upload_info = upload_processed_file_to_space(final_video_local_path, processed_object_name)

        record.status = "COMPLETED"
        record.public_url = final_upload_info["public_url"]
        record.file_path = final_upload_info["public_url"]
        record.summary = summary_text
        db.add(record)
        db.commit()
        db.refresh(record)
        db.commit()

    except Exception as e:
        record.status = "FAILED"
        record.error_message = str(e)
        db.commit()
        raise e
    finally:
        db.close()


@celery_app.task(bind=True)
def process_audio_task(self, job_id: int, object_name: str, options: dict, user_id: int):
    return asyncio.run(_process_audio_async(job_id, object_name, options, user_id))


@celery_app.task(bind=True)
def process_video_task(self, job_id: int, object_name: str, options: dict, user_id: int):
    return asyncio.run(_process_video_async(job_id, object_name, options, user_id))


# @celery_app.task(name="cleanup_old_files")
# def cleanup_old_files_task():
#     """
#     Finds and deletes files and their DB records that are older than 1 day.
#     This task is designed to be run on a schedule by Celery Beat.
#     """
#     print("--- Running scheduled cleanup task ---")
#     db = SessionLocal()
#     try:
#         # Define the cutoff time (anything created before this will be deleted)
#         one_day_ago = datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
#
#         # Query for old audio and video records
#         old_audios = db.query(Audio).filter(Audio.uploaded_at < one_day_ago).all()
#         old_videos = db.query(Video).filter(Video.uploaded_at < one_day_ago).all()
#
#         all_old_records = old_audios + old_videos
#
#         if not all_old_records:
#             print("No old files found to delete.")
#             return "No old files found."
#
#         print(f"Found {len(all_old_records)} old records to delete.")
#
#         deleted_count = 0
#         for record in all_old_records:
#             if record.object_name:
#                 # First, delete the file from cloud storage
#                 success = delete_file_from_space(record.object_name)
#
#                 # IMPORTANT: Only delete the DB record if the file was deleted from storage
#                 if success:
#                     print(f"Deleting DB record ID {record.id}...")
#                     db.delete(record)
#                     deleted_count += 1
#
#         # Commit all deletions at once
#         db.commit()
#         print(f"Cleanup complete. Deleted {deleted_count} files and records.")
#         return f"Cleanup complete. Deleted {deleted_count} files."
#
#     finally:
#         db.close()
#