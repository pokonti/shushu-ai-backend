import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any

from celery import current_task
from google.cloud import storage

from src.worker.celery_app import celery_app
from src.preprocessing.denoiser import denoise_audio
from src.preprocessing.filler import get_filler_timestamps_from_audio, remove_filler_words_from_audio, \
    remove_filler_words_smooth
from src.summary.service import get_summary
from src.media.service import extract_audio_from_video, replace_audio_in_video

BUCKET_NAME = os.getenv("BUCKET_NAME")


def download_from_gcs(gcs_uri: str, local_path: str) -> str:
    """Download file from GCS to local temp directory"""
    client = storage.Client()

    # Parse GCS URI (gs://bucket/path)
    gcs_path = gcs_uri.replace("gs://", "")
    bucket_name, blob_name = gcs_path.split("/", 1)

    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Ensure directory exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    blob.download_to_filename(local_path)
    return local_path


def upload_processed_file_to_gcs(local_path: str, user_id: int, file_type: str = "processed") -> tuple[str, str]:
    """Upload processed file back to GCS"""
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    # Get file extension
    ext = Path(local_path).suffix

    # Create unique blob name
    blob_name = f"{file_type}/user_{user_id}/{uuid.uuid4()}{ext}"
    blob = bucket.blob(blob_name)

    # Upload file
    blob.upload_from_filename(local_path)
    blob.make_public()

    return blob.public_url, f"gs://{BUCKET_NAME}/{blob_name}"


@celery_app.task(bind=True)
def debug_add(self, x: int, y: int) -> int:
    """Simple test task"""
    return x + y


@celery_app.task(bind=True)
def process_audio_task(self, gcs_uri: str, user_id: int, processing_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process audio file: download -> process -> upload

    Args:
        gcs_uri: GCS URI of the original file
        user_id: User ID for organizing files
        processing_options: Dict with keys: denoise, remove_fillers, summarize
    """
    try:
        # Update task state
        self.update_state(state='PROCESSING', meta={'status': 'Downloading file from GCS'})

        # Create temp directory for this task
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Download original file
            original_filename = f"original_audio_{uuid.uuid4()}.mp3"
            original_path = temp_dir_path / original_filename
            download_from_gcs(gcs_uri, str(original_path))

            current_file_path = str(original_path)
            result_data = {
                "original_gcs_uri": gcs_uri,
                "processing_steps": []
            }

            # Process: Denoise
            if processing_options.get("denoise", False):
                self.update_state(state='PROCESSING', meta={'status': 'Denoising audio'})
                try:
                    denoised_path = denoise_audio(current_file_path)
                    current_file_path = denoised_path
                    result_data["processing_steps"].append("denoise")
                except Exception as e:
                    result_data["errors"] = result_data.get("errors", [])
                    result_data["errors"].append(f"Denoise failed: {str(e)}")

            # Process: Remove fillers
            if processing_options.get("remove_fillers", False):
                self.update_state(state='PROCESSING', meta={'status': 'Removing filler words'})
                try:
                    filler_times = get_filler_timestamps_from_audio(current_file_path)
                    cleaned_path = remove_filler_words_from_audio(current_file_path, filler_times)
                    current_file_path = cleaned_path
                    result_data["filler_timestamps"] = filler_times
                    result_data["processing_steps"].append("remove_fillers")
                except Exception as e:
                    result_data["errors"] = result_data.get("errors", [])
                    result_data["errors"].append(f"Filler removal failed: {str(e)}")

            # Process: Summarize
            if processing_options.get("summarize", False):
                self.update_state(state='PROCESSING', meta={'status': 'Generating summary'})
                try:
                    summary = get_summary(current_file_path)
                    result_data["summary"] = summary
                    result_data["processing_steps"].append("summarize")
                except Exception as e:
                    result_data["errors"] = result_data.get("errors", [])
                    result_data["errors"].append(f"Summarization failed: {str(e)}")

            # Upload processed file back to GCS
            self.update_state(state='PROCESSING', meta={'status': 'Uploading processed file'})
            public_url, processed_gcs_uri = upload_processed_file_to_gcs(
                current_file_path, user_id, "processed_audio"
            )

            result_data.update({
                "processed_public_url": public_url,
                "processed_gcs_uri": processed_gcs_uri,
                "status": "completed"
            })

            return result_data

    except Exception as e:
        # Update task state with error
        self.update_state(
            state='FAILURE',
            meta={'status': 'Error occurred', 'error': str(e)}
        )
        raise


@celery_app.task(bind=True)
def process_video_task(self, gcs_uri: str, user_id: int, processing_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process video file: download -> extract audio -> process -> replace audio -> upload

    Args:
        gcs_uri: GCS URI of the original video file
        user_id: User ID for organizing files
        processing_options: Dict with keys: denoise, remove_fillers, summarize
    """
    try:
        # Update task state
        self.update_state(state='PROCESSING', meta={'status': 'Downloading video from GCS'})

        # Create temp directory for this task
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Download original video
            original_filename = f"original_video_{uuid.uuid4()}.mp4"
            original_video_path = temp_dir_path / original_filename
            download_from_gcs(gcs_uri, str(original_video_path))

            # Extract audio from video
            self.update_state(state='PROCESSING', meta={'status': 'Extracting audio from video'})
            audio_path = extract_audio_from_video(str(original_video_path))

            current_video_path = str(original_video_path)
            current_audio_path = audio_path

            result_data = {
                "original_gcs_uri": gcs_uri,
                "processing_steps": []
            }

            # Process: Denoise
            if processing_options.get("denoise", False):
                self.update_state(state='PROCESSING', meta={'status': 'Denoising audio'})
                try:
                    denoised_audio_path = denoise_audio(current_audio_path)
                    current_video_path = replace_audio_in_video(current_video_path, denoised_audio_path)
                    current_audio_path = denoised_audio_path
                    result_data["processing_steps"].append("denoise")
                except Exception as e:
                    result_data["errors"] = result_data.get("errors", [])
                    result_data["errors"].append(f"Denoise failed: {str(e)}")

            # Process: Remove fillers
            if processing_options.get("remove_fillers", False):
                self.update_state(state='PROCESSING', meta={'status': 'Removing filler words'})
                try:
                    filler_times = get_filler_timestamps_from_audio(current_audio_path)
                    cleaned_audio_path = remove_filler_words_from_audio(current_audio_path, filler_times)
                    cleaned_video_path = remove_filler_words_smooth(current_video_path, filler_times)

                    current_video_path = cleaned_video_path
                    current_audio_path = cleaned_audio_path
                    result_data["filler_timestamps"] = filler_times
                    result_data["processing_steps"].append("remove_fillers")
                except Exception as e:
                    result_data["errors"] = result_data.get("errors", [])
                    result_data["errors"].append(f"Filler removal failed: {str(e)}")

            # Process: Summarize
            if processing_options.get("summarize", False):
                self.update_state(state='PROCESSING', meta={'status': 'Generating summary'})
                try:
                    summary = get_summary(current_audio_path)
                    result_data["summary"] = summary
                    result_data["processing_steps"].append("summarize")
                except Exception as e:
                    result_data["errors"] = result_data.get("errors", [])
                    result_data["errors"].append(f"Summarization failed: {str(e)}")

            # Upload processed video back to GCS
            self.update_state(state='PROCESSING', meta={'status': 'Uploading processed video'})
            public_url, processed_gcs_uri = upload_processed_file_to_gcs(
                current_video_path, user_id, "processed_video"
            )

            result_data.update({
                "processed_public_url": public_url,
                "processed_gcs_uri": processed_gcs_uri,
                "status": "completed"
            })

            return result_data

    except Exception as e:
        # Update task state with error
        self.update_state(
            state='FAILURE',
            meta={'status': 'Error occurred', 'error': str(e)}
        )
        raise



