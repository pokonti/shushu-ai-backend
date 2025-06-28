import os
from celery import current_task
from src.database import SessionLocal
from src.media.models import Audio, Video
from src.preprocessing.denoiser import process_audio_from_url
from src.space.service import upload_processed_file_to_space
from src.worker.celery_app import celery_app
import httpx
from tempfile import TemporaryDirectory
import asyncio

# Helper to run async code inside a sync Celery task
def run_async(task):
    return asyncio.run(task)


@celery_app.task(bind=True)
def debug_add(self, x: int, y: int) -> int:
    """Simple test task"""
    return x + y


@celery_app.task
def process_file_task(job_id: int, model_name: str, object_name: str, options: dict):
    """
    This runs in the background. It does all the slow work.
    """
    db = SessionLocal()
    Model = Audio if model_name == "Audio" else Video
    record = db.query(Model).filter(Model.id == job_id).first()

    if not record:
        print(f"Job {job_id} not found. Aborting.")
        return

    try:
        # Update status to show work has started
        record.status = "PROCESSING"
        db.commit()

        # ALL YOUR SLOW LOGIC FROM THE OLD ENDPOINT GOES HERE
        with TemporaryDirectory() as temp_dir:
            original_public_url = f"https://{os.getenv('DO_SPACES_BUCKET_NAME')}.{os.getenv('DO_SPACES_REGION')}.cdn.digitaloceanspaces.com/{object_name}"

            # --- Logic for Audio Files ---
            if model_name == "Audio":
                # Run the async Cleanvoice poller
                cleaned_audio_url = run_async(process_audio_from_url(original_public_url, options))

                # Download the final, cleaned audio file from Cleanvoice
                local_final_path = os.path.join(temp_dir, f"processed_{os.path.basename(object_name)}")

                async def download_final_file():
                    async with httpx.AsyncClient() as client:
                        response = await client.get(cleaned_audio_url)
                        with open(local_final_path, 'wb') as f:
                            f.write(response.content)

                run_async(download_final_file())
                final_file_to_upload = local_final_path

            # --- Logic for Video Files ---
            else:
                # ... your video logic here ...
                final_file_to_upload = ...

            # UPLOAD THE PROCESSED FILE BACK TO YOUR SPACES
            processed_object_name = object_name.replace("originals/", "processed/")
            upload_info = upload_processed_file_to_space(final_file_to_upload, processed_object_name)

        # 4. UPDATE THE DATABASE WITH THE FINAL RESULT
        record.status = "COMPLETED"
        record.public_url = upload_info["public_url"]
        record.file_path = upload_info["public_url"]
        record.gcs_uri = upload_info["spaces_uri"]
        # record.summary = ... # Add summary logic if you have it
        db.commit()

    except Exception as e:
        # If anything goes wrong, record the failure
        record.status = "FAILED"
        record.error_message = str(e)
        db.commit()
    finally:
        db.close()