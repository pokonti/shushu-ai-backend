import datetime
import os
import time
from pathlib import Path

from celery import current_task
from pip._internal.utils import temp_dir

from src.auth.models import User
from src.database import SessionLocal
from src.media.models import Audio, Video
from src.media.service import extract_audio_from_video, replace_audio_in_video
from src.preprocessing.denoiser import process_audio_from_url
from src.preprocessing.filler import remove_filler_words_from_audio, get_filler_timestamps_from_audio, \
    remove_filler_words_smooth
from src.shorts.ai.service import get_info_for_shorts, extract_json_from_gpt_response, transcribe_audio
from src.shorts.broll.service import search_broll_videos, download_broll_videos, prepare_broll_insertions, \
    concat_with_broll_ffmpeg, assemble_video_with_broll_overlay, concat_with_broll_ffmpeg_light
from src.space.service import upload_processed_file_to_space, download_file_from_space, delete_file_from_space

from src.worker.celery_app import celery_app
import httpx
from tempfile import TemporaryDirectory
import asyncio
import shutil
import uuid
import json

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

            # Upload the final version of the file, whatever it may be.
            print(f"Uploading final processed file '{current_file_path}' to Spaces...")
            processed_object_name = object_name.replace("originals/", "processed/")
            final_upload_info = upload_processed_file_to_space(current_file_path, processed_object_name)

        record.status = "COMPLETED"
        record.public_url = final_upload_info["public_url"]
        record.file_path = final_upload_info["public_url"]
        db.commit()
        return {"status": "COMPLETED", "public_url": record.public_url}

    except Exception as e:
        record.status = "FAILED"
        record.error_message = str(e)
        db.commit()
        raise e
    finally:
        db.close()

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


            # Recombine the final processed audio with the original video.
            print(f"Recombining final audio ('{os.path.basename(current_audio_path)}') with original video...")
            final_video_local_path = replace_audio_in_video(current_video_path, current_audio_path, temp_dir)
            # Upload the final video file to Spaces.
            print(f"Uploading final processed video '{os.path.basename(final_video_local_path)}' to Spaces...")
            processed_object_name = object_name.replace("originals/", "processed/")
            final_upload_info = upload_processed_file_to_space(final_video_local_path, processed_object_name)

        record.status = "COMPLETED"
        record.public_url = final_upload_info["public_url"]
        record.file_path = final_upload_info["public_url"]
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
def start_shorts_analysis_task(self, job_id: int, object_name: str, user_id: int):
    """
    Task 1: Downloads, transcribes, and gets AI suggestions.
    This task is CPU-intensive due to transcription but not for a long duration.
    """
    db = SessionLocal()
    record = db.query(Video).filter(Video.id == job_id).first()
    if not record:
        print(f"Job {job_id}: Record not found. Aborting.")
        return

    # Create a unique, persistent staging directory for this job's files.
    staging_dir = f"/tmp/shushu_job_{job_id}"
    os.makedirs(staging_dir, exist_ok=True)

    try:
        record.status = "ANALYZING"
        db.commit()

        # Download original video to the staging directory
        original_video_path = os.path.join(staging_dir, os.path.basename(object_name))
        download_file_from_space(object_name, original_video_path)

        # Extract audio for processing
        extracted_audio_path = extract_audio_from_video(original_video_path)

        # Transcribe locally using the pre-loaded Faster Whisper model
        # transcription_data = transcribe_audio(Path(extracted_audio_path), model_size="base")

        moments_data = get_info_for_shorts(extracted_audio_path)
        segments = moments_data.model_dump()

        moments_file_path = os.path.join(staging_dir, "moments.json")

        with open(moments_file_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)

        # Update status and trigger the next task in the chain
        record.status = "DOWNLOADING_BROLL"
        db.commit()
        download_broll_task.delay(job_id, staging_dir, moments_file_path)
        print(f"Job {job_id}: Analysis complete. Triggering B-roll download.")

    except Exception as e:
        record.status = "FAILED"
        record.error_message = f"Analysis Failed: {str(e)}"
        db.commit()
        # Clean up staging directory on failure
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
        raise e
    finally:
        db.close()

def wait_for_valid_json(path, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        if not os.path.exists(path):
            time.sleep(0.1)
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    raise ValueError("Empty file")
                data = json.loads(content)
                if "moments" not in data:
                    raise KeyError("'moments' key not in data")
                return data
        except (json.JSONDecodeError, ValueError, KeyError):
            time.sleep(0.1)
    raise TimeoutError(f"moments.json was not valid after {timeout}s")

# ==============================================================================
#   TASK 2: B-roll Downloading - Handles all network I/O.
# ==============================================================================
@celery_app.task(bind=True)
def download_broll_task(self, job_id: int, staging_dir: str, moments_file_path: str):
    """
    Task 2: Reads the moments file, searches Pexels, and downloads B-roll videos.
    This task is network-bound.
    """
    db = SessionLocal()
    record = db.query(Video).filter(Video.id == job_id).first()
    try:
        moments = wait_for_valid_json(moments_file_path)

        all_video_matches = []

        for item in moments["moments"]:
            # found_videos = search_broll_videos(item["keywords"])
            # if found_videos:
                # Add the moment's timestamp to the video data for later use
                keywords = item["keywords"]
                timestamp = item["timestamp"]
                broll_videos = search_broll_videos(keywords)

                all_video_matches.append({
                    "timestamp": timestamp,
                    "keywords": keywords,
                    "videos": broll_videos  # List of matching videos from Pexels
                })

        # downloaded_data = asyncio.run(download_broll_videos(all_video_matches, staging_dir))

        downloaded_paths = asyncio.run(download_broll_videos(all_video_matches, staging_dir))

        # Step 3: Save mapping (timestamp <-> broll_path) to a JSON file
        broll_paths_file = os.path.join(staging_dir, "broll_paths.json")
        final_broll_info = []

        for i, group in enumerate(all_video_matches):
            timestamp = group["timestamp"]
            keywords = group["keywords"]

            # Build same filename as in download function
            if group["videos"]:
                keyword = group["videos"][0].get("keyword", "clip").replace(" ", "_")
                ext = Path(group["videos"][0]["download_url"]).suffix or ".mp4"
                expected_filename = f"group{i}_{keyword}{ext}"
                local_path = os.path.join(staging_dir, expected_filename)

                if os.path.exists(local_path):
                    final_broll_info.append({
                        "broll_path": local_path,
                        "timestamp": timestamp
                    })
                else:
                    print(f"⚠️ Expected file not found: {expected_filename}")

        # Step 4: Write to file
        with open(broll_paths_file, "w", encoding="utf-8") as f:
            json.dump(final_broll_info, f, indent=2)

        # Step 5: Trigger final assembly
        record.status = "ASSEMBLING"
        db.commit()
        assemble_video_task.delay(job_id, staging_dir, broll_paths_file)

    except Exception as e:
        record.status = "FAILED"
        record.error_message = f"B-roll Download Failed: {str(e)}"
        db.commit()
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
        raise e
    finally:
        db.close()


# ==============================================================================
#   TASK 3: Video Assembly - The heavy CPU work.
# ==============================================================================
@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def assemble_video_task(self, job_id: int, staging_dir: str, broll_paths_file: str):
    """
    Task 3: Reads all files from the staging directory and uses FFmpeg
    to assemble the final video. This is a CPU-intensive task.
    """
    db = SessionLocal()
    record = db.query(Video).filter(Video.id == job_id).first()

    try:
        with open(broll_paths_file, "r") as f:
            broll_insertions = json.load(f)

        original_video_path = os.path.join(staging_dir, os.path.basename(record.object_name))
        final_output_path = os.path.join(staging_dir, "final_video.mp4")

        # Call the high-performance FFmpeg assembly function
        assemble_video_with_broll_overlay(original_video_path, broll_insertions, final_output_path)

        # Upload the final video to cloud storage
        processed_object_name = record.object_name.replace("originals/", "processed/")
        final_upload_info = upload_processed_file_to_space(final_output_path, processed_object_name)

        # Final database update to mark the job as complete
        record.status = "COMPLETED"
        record.public_url = final_upload_info["public_url"]
        record.file_path = final_upload_info["public_url"]
        db.commit()
        print(f"Job {job_id}: Assembly complete. Final video uploaded.")

    except Exception as e:
        record.status = "FAILED"
        record.error_message = f"Assembly Failed: {str(e)}"
        db.commit()
        raise e
    finally:
        db.close()
        # Clean up the staging directory now that the job is finished
        if os.path.exists(staging_dir):
            print(f"Cleaning up staging directory: {staging_dir}")
            shutil.rmtree(staging_dir)


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def process_audio_task(self, job_id: int, object_name: str, options: dict, user_id: int):
    return asyncio.run(_process_audio_async(job_id, object_name, options, user_id))


@celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
def process_video_task(self, job_id: int, object_name: str, options: dict, user_id: int):
    return asyncio.run(_process_video_async(job_id, object_name, options, user_id))


# @celery_app.task(bind=True, soft_time_limit=3600, time_limit=3660)
# def process_shorts_task(self, job_id: int, object_name: str, user_id: int):
#     return asyncio.run(_process_shorts_async(job_id, object_name, user_id))

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