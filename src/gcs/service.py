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

# Configuration
BUCKET_NAME = os.getenv("BUCKET_NAME")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Allowed file types
ALLOWED_VIDEO_TYPES = {
    "media/mp4", "media/mov",
    "media/flv", "media/webm", "media/mkv"
}
ALLOWED_AUDIO_TYPES = {
    "audio/mp3", "audio/wav", "audio/aac",
    "audio/ogg", "audio/m4a", "audio/wma"
}

# File size limits (in bytes)
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB
MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100MB


class GCSManager:
    def __init__(self):
        self.client = storage.Client()
        self.bucket = self.client.bucket(BUCKET_NAME)

    def upload_file(self, file_content: bytes, file_name: str, content_type: str) -> str:
        """Upload file to GCS and return public URL"""
        try:
            blob = self.bucket.blob(file_name)
            blob.upload_from_string(file_content, content_type=content_type)

            # Make the blob publicly accessible (optional)
            blob.make_public()

            return blob.public_url
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    def delete_file(self, file_name: str) -> bool:
        """Delete file from GCS"""
        try:
            blob = self.bucket.blob(file_name)
            blob.delete()
            return True
        except NotFound:
            return False
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

    def generate_signed_url(self, file_name: str, expiration_hours: int = 1) -> str:
        """Generate a signed URL for private file access"""
        try:
            blob = self.bucket.blob(file_name)
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.utcnow() + timedelta(hours=expiration_hours),
                method="GET"
            )
            return url
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"URL generation failed: {str(e)}")


# Dependency to get GCS manager
def get_gcs_manager():
    return GCSManager()


def validate_file(file: UploadFile, allowed_types: set, max_size: int):
    """Validate file type and size"""
    # Check content type
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )

    # Check file size (this is approximate, actual size checked during upload)
    if hasattr(file, 'size') and file.size and file.size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_size // (1024 * 1024)}MB"
        )


def generate_unique_filename(original_filename: str, file_type: str) -> str:
    """Generate unique filename with proper directory structure"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    file_extension = os.path.splitext(original_filename)[1]

    return f"{file_type}/{timestamp}_{unique_id}_{original_filename}"


# @app.post("/upload/media")
async def upload_video(
        file: UploadFile = File(...),
        gcs_manager: GCSManager = Depends(get_gcs_manager)
):
    """Upload media file to Google Cloud Storage"""
    validate_file(file, ALLOWED_VIDEO_TYPES, MAX_VIDEO_SIZE)

    try:
        # Read file content
        content = await file.read()

        # Check actual file size
        if len(content) > MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_VIDEO_SIZE // (1024 * 1024)}MB"
            )

        # Generate unique filename
        filename = generate_unique_filename(file.filename, "videos")

        # Upload to GCS
        public_url = gcs_manager.upload_file(content, filename, file.content_type)

        return JSONResponse({
            "message": "Video uploaded successfully",
            "filename": filename,
            "original_filename": file.filename,
            "public_url": public_url,
            "file_size": len(content),
            "content_type": file.content_type
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# @app.post("/upload/audio")
async def upload_audio(
        file: UploadFile = File(...),
        gcs_manager: GCSManager = Depends(get_gcs_manager)
):
    """Upload audio file to Google Cloud Storage"""
    validate_file(file, ALLOWED_AUDIO_TYPES, MAX_AUDIO_SIZE)

    try:
        # Read file content
        content = await file.read()

        # Check actual file size
        if len(content) > MAX_AUDIO_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_AUDIO_SIZE // (1024 * 1024)}MB"
            )

        # Generate unique filename
        filename = generate_unique_filename(file.filename, "audios")

        # Upload to GCS
        public_url = gcs_manager.upload_file(content, filename, file.content_type)

        return JSONResponse({
            "message": "Audio uploaded successfully",
            "filename": filename,
            "original_filename": file.filename,
            "public_url": public_url,
            "file_size": len(content),
            "content_type": file.content_type
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# @app.post("/upload/multiple")
async def upload_multiple_files(
        files: List[UploadFile] = File(...),
        gcs_manager: GCSManager = Depends(get_gcs_manager)
):
    """Upload multiple media/audio files"""
    if len(files) > 10:  # Limit number of files
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed")

    results = []
    errors = []

    for file in files:
        try:
            # Determine file type
            if file.content_type in ALLOWED_VIDEO_TYPES:
                validate_file(file, ALLOWED_VIDEO_TYPES, MAX_VIDEO_SIZE)
                folder = "videos"
                max_size = MAX_VIDEO_SIZE
            elif file.content_type in ALLOWED_AUDIO_TYPES:
                validate_file(file, ALLOWED_AUDIO_TYPES, MAX_AUDIO_SIZE)
                folder = "audios"
                max_size = MAX_AUDIO_SIZE
            else:
                errors.append({
                    "filename": file.filename,
                    "error": "Invalid file type"
                })
                continue

            # Read and validate file content
            content = await file.read()
            if len(content) > max_size:
                errors.append({
                    "filename": file.filename,
                    "error": f"File too large. Maximum size: {max_size // (1024 * 1024)}MB"
                })
                continue

            # Generate unique filename and upload
            filename = generate_unique_filename(file.filename, folder)
            public_url = gcs_manager.upload_file(content, filename, file.content_type)

            results.append({
                "filename": filename,
                "original_filename": file.filename,
                "public_url": public_url,
                "file_size": len(content),
                "content_type": file.content_type
            })

        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })

    return JSONResponse({
        "message": f"Processed {len(files)} files",
        "successful_uploads": len(results),
        "failed_uploads": len(errors),
        "results": results,
        "errors": errors
    })


# @app.delete("/delete/{file_path:path}")
async def delete_file(
        file_path: str,
        gcs_manager: GCSManager = Depends(get_gcs_manager)
):
    """Delete file from Google Cloud Storage"""
    success = gcs_manager.delete_file(file_path)

    if success:
        return JSONResponse({"message": "File deleted successfully"})
    else:
        raise HTTPException(status_code=404, detail="File not found")


# @app.get("/signed-url/{file_path:path}")
async def get_signed_url(
        file_path: str,
        expiration_hours: int = 1,
        gcs_manager: GCSManager = Depends(get_gcs_manager)
):
    """Get signed URL for private file access"""
    if expiration_hours > 24:
        raise HTTPException(status_code=400, detail="Maximum expiration is 24 hours")

    signed_url = gcs_manager.generate_signed_url(file_path, expiration_hours)

    return JSONResponse({
        "signed_url": signed_url,
        "expiration_hours": expiration_hours
    })


def create_bucket(bucket_name, storage_class='STANDARD', location='us-central1'):
    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    bucket.storage_class = storage_class

    bucket = storage_client.create_bucket(bucket, location=location)
    # for dual-location buckets add data_locations=[region_1, region_2]

    return f'Bucket {bucket.name} successfully created.'


def upload_video_to_gcs(file: UploadFile, user_id: int) -> str:
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    ext = file.filename.split(".")[-1]
    blob_name = f"media/user_{user_id}/{uuid.uuid4()}.{ext}"
    blob = bucket.blob(blob_name)

    file.file.seek(0)
    blob.upload_from_file(file.file, content_type=file.content_type)
    blob.make_public()

    return blob.public_url, f"gs://{BUCKET_NAME}/{blob_name}"

def upload_audio_to_gcs(file: UploadFile, user_id: int) -> str:
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    ext = file.filename.split(".")[-1]
    blob_name = f"audio/user_{user_id}/{uuid.uuid4()}.{ext}"
    blob = bucket.blob(blob_name)

    file.file.seek(0)
    blob.upload_from_file(file.file, content_type=file.content_type)
    blob.make_public()

    return blob.public_url, f"gs://{BUCKET_NAME}/{blob_name}"

def get_from_gcs(user_id: int) -> List[str]:
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    prefix = f"media/user_{user_id}/"

    # list all blobs under that prefix
    blobs = bucket.list_blobs(prefix=prefix)

    # return each blob’s public URL
    return [blob.public_url for blob in blobs]

