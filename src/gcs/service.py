import os
import uuid
from typing import List
from datetime import datetime, timedelta

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from google.cloud import storage
from google.cloud.exceptions import NotFound
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

def create_bucket(bucket_name, storage_class='STANDARD', location='us-central1'):
    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    bucket.storage_class = storage_class

    bucket = storage_client.create_bucket(bucket, location=location)
    # for dual-location buckets add data_locations=[region_1, region_2]

    return f'Bucket {bucket.name} successfully created.'


def upload_to_gcs(file: UploadFile, user_id: int, audio: bool = True) -> tuple[str, str]:
    """
    Upload audio file to Google Cloud Storage

    Args:
        file: FastAPI UploadFile object
        user_id: User ID for organizing files

    Returns:
        tuple: (public_url, gcs_uri)
    """
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)

        if audio:
            # Get file extension
            ext = file.filename.split(".")[-1] if "." in file.filename else "wav"
            # Create unique blob name with user organization
            blob_name = f"audios/user_{user_id}/{uuid.uuid4()}.{ext}"
        else:
            ext = file.filename.split(".")[-1] if "." in file.filename else "mp4"
            blob_name = f"videos/user_{user_id}/{uuid.uuid4()}.{ext}"

        blob = bucket.blob(blob_name)

        # Reset file pointer to beginning
        file.file.seek(0)

        # Upload file with proper content type
        blob.upload_from_file(file.file, content_type=file.content_type)

        # Make blob publicly accessible
        blob.make_public()

        # Return public URL and GCS URI
        public_url = blob.public_url
        gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"

        return public_url, gcs_uri

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio upload to GCS failed: {str(e)}")


def get_user_media_from_gcs(user_id: int, media_type: str = "videos") -> List[str]:
    """
    Get all media files for a specific user from GCS

    Args:
        user_id: User ID
        media_type: "videos" or "audio" or "processed_video" or "processed_audio"

    Returns:
        List of public URLs
    """
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)

        # Set prefix based on media type
        prefix = f"{media_type}/user_{user_id}/"

        # List all blobs under that prefix
        blobs = bucket.list_blobs(prefix=prefix)

        # Return each blob's public URL
        return [blob.public_url for blob in blobs if blob.name != prefix]  # Exclude folder itself

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve media from GCS: {str(e)}")


def delete_file_from_gcs(gcs_uri: str) -> bool:
    """
    Delete a file from Google Cloud Storage

    Args:
        gcs_uri: Full GCS URI (gs://bucket/path)

    Returns:
        bool: True if successful, False if file not found
    """
    try:
        client = storage.Client()

        # Parse GCS URI
        gcs_path = gcs_uri.replace("gs://", "")
        bucket_name, blob_name = gcs_path.split("/", 1)

        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Delete the blob
        blob.delete()
        return True

    except Exception as e:
        # Log the error if you have logging set up
        print(f"Failed to delete file from GCS: {str(e)}")
        return False