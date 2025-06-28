from fastapi import APIRouter, HTTPException, Depends, Body
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




# @router.post("/process-file")
# async def process_file(
#         object_name: str = Body(..., embed=True),
#         options: dict = Body(..., embed=True),
#         db: Session = Depends(get_db),
#         user: User = Depends(get_current_user)
# ):
#     # This endpoint is now async because it calls our async cleanvoice function
#     is_video = object_name.endswith((".mp4", ".mov", ".mkv"))
#
#     # Construct the public URL of the file you just uploaded to your Space
#     original_public_url = f"https://{os.getenv('DO_SPACES_BUCKET_NAME')}.{os.getenv('DO_SPACES_REGION')}.cdn.digitaloceanspaces.com/{object_name}"
#
#     with TemporaryDirectory() as temp_dir:
#         # --- Logic for Audio Files ---
#         if not is_video:
#             # 1. Process via Cleanvoice using the public URL
#             cleaned_audio_url = await process_audio_from_url(original_public_url, options)
#
#             # 2. Download the final, cleaned audio file from Cleanvoice
#             local_final_path = os.path.join(temp_dir, f"processed_{os.path.basename(object_name)}")
#             async with httpx.AsyncClient() as client:
#                 response = await client.get(cleaned_audio_url)
#                 with open(local_final_path, 'wb') as f:
#                     f.write(response.content)
#
#             final_file_to_upload = local_final_path
#             summary = None  # Add summary logic if needed
#
#         # --- Logic for Video Files (More complex) ---
#         else:
#             # For video, you first need to extract the audio, upload IT to spaces,
#             # then process IT, then recombine. This is more complex.
#             # Let's focus on getting audio working first.
#             # For now, we just pass through the video
#             # Download the original video to pass it through
#             download_file_from_space(object_name, os.path.join(temp_dir, "video.mp4"))
#             final_file_to_upload = os.path.join(temp_dir, "video.mp4")
#             summary = None
#
#         # 3. UPLOAD THE PROCESSED FILE BACK TO YOUR SPACES
#         processed_object_name = object_name.replace("originals/", "processed/")
#         upload_info = upload_processed_file_to_space(final_file_to_upload, processed_object_name)
#
#     # 4. SAVE THE FINAL RESULT TO THE DATABASE
#     Model = Video if is_video else Audio
#     record = Model(
#         user_id=user.id,
#         file_path=upload_info["public_url"],
#         gcs_uri=upload_info["spaces_uri"],  # Rename this column later
#         public_url=upload_info["public_url"],
#         summary=summary
#     )
#
#     db.add(record)
#     db.commit()
#     db.refresh(record)
#
#     return {
#         "message": "Processing complete!",
#         "result": {
#             "public_url": record.public_url,
#             "summary": record.summary
#         }
#     }




# @router.post("/generate-upload-url")
# def generate_upload_url(filename: str = Body(..., embed=True), user: User = Depends(get_current_user)):
#     """ENDPOINT 1: The frontend calls this first to get permission to upload."""
#     url_data = create_resigned_upload_url(user_id=user.id, file_name=filename)
#     if not url_data:
#         raise HTTPException(status_code=500, detail="Could not create upload URL")
#     return url_data


# @router.post("/process-file")
# async def process_file(
#         object_name: str = Body(..., embed=True),
#         options: dict = Body(..., embed=True),
#         db: Session = Depends(get_db),
#         user: User = Depends(get_current_user)
# ):
#     """
#     ENDPOINT 2: Frontend calls this after upload.
#     WARNING: This endpoint is VERY SLOW and will time out on a real server.
#              It is for local testing only. The logic here MUST be moved to a Celery worker.
#     """
#     is_video = object_name.endswith((".mp4", ".mov", ".mkv"))
#     Model = Video if is_video else Audio
#
#     with TemporaryDirectory() as temp_dir:
#         # --- Common Path for All Files: Where is the audio to process? ---
#         audio_to_process_url = ""
#         original_video_local_path = ""  # Needed for video to recombine later
#
#         if is_video:
#             print("Processing video file...")
#             # 1. Download the original video from Spaces
#             original_video_local_path = os.path.join(temp_dir, os.path.basename(object_name))
#             download_file_from_space(object_name, original_video_local_path)
#
#             # 2. Extract the audio from it
#             extracted_audio_local_path = extract_audio_from_video(original_video_local_path)
#
#             # 3. CRITICAL STEP: Upload the extracted audio to Spaces to get a public URL
#             audio_object_name = f"users/{user.id}/temp/{os.path.basename(extracted_audio_local_path)}"
#             audio_upload_info = upload_processed_file_to_space(extracted_audio_local_path, audio_object_name)
#             audio_to_process_url = audio_upload_info["public_url"]
#             print(f"Temporarily uploaded extracted audio to: {audio_to_process_url}")
#         else:
#             print("Processing audio file...")
#             # For audio files, the public URL is simple to construct
#             audio_to_process_url = f"https://{os.getenv('DO_SPACES_BUCKET_NAME')}.{os.getenv('DO_SPACES_REGION')}.cdn.digitaloceanspaces.com/{object_name}"
#
#         # --- Universal Processing Step using Cleanvoice ---
#         print("Sending audio to Cleanvoice for processing...")
#         processed_audio_url_from_cleanvoice = await process_audio_from_url(audio_to_process_url, options)
#
#         # Download the final, cleaned audio file from Cleanvoice
#         processed_audio_local_path = os.path.join(temp_dir, "final_processed_audio.wav")
#         async with httpx.AsyncClient() as client:
#             response = await client.get(processed_audio_url_from_cleanvoice)
#             with open(processed_audio_local_path, 'wb') as f:
#                 f.write(response.content)
#         print(f"Downloaded processed audio to: {processed_audio_local_path}")
#
#         # --- Final Assembly and Upload ---
#         final_file_to_upload_path = ""
#         if is_video:
#             # Recombine the processed audio with the original video
#             print("Recombining processed audio with original video...")
#             final_video_local_path = replace_audio_in_video(original_video_local_path, processed_audio_local_path)
#             final_file_to_upload_path = final_video_local_path
#         else:
#             # For audio, the downloaded processed file is the final file
#             final_file_to_upload_path = processed_audio_local_path
#
#         # UPLOAD THE PROCESSED FILE BACK TO YOUR SPACES
#         processed_object_name = object_name.replace("originals/", "processed/")
#         final_upload_info = upload_processed_file_to_space(final_file_to_upload_path, processed_object_name)
#
#     # SAVE THE FINAL RESULT TO THE DATABASE
#     record = Model(
#         user_id=user.id,
#         file_path=final_upload_info["public_url"],
#         object_name=final_upload_info["spaces_uri"],  # This should be renamed to 'object_name' or similar
#         public_url=final_upload_info["public_url"],
#     )
#     db.add(record)
#     db.commit()
#
#     return {
#         "message": "Processing complete!",
#         "result": {"public_url": final_upload_info["public_url"]}
#     }
@router.post("/process-audio")
async def process_audio(
        object_name: str = Body(..., embed=True),
        options: dict = Body(..., embed=True),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    """
    Processes a pure audio file.
    Workflow: Get Public URL -> Cleanvoice -> Download -> Upload Final -> Save DB.
    """
    with TemporaryDirectory() as temp_dir:
        # 1. Construct the public URL of the original audio file in Spaces
        original_public_url = f"https://{os.getenv('DO_SPACES_BUCKET_NAME')}.{os.getenv('DO_SPACES_REGION')}.cdn.digitaloceanspaces.com/{object_name}"

        # 2. Process via Cleanvoice using the public URL
        print(f"Sending audio {original_public_url} to Cleanvoice...")
        processed_audio_url = await process_audio_from_url(original_public_url, options)

        # 3. Download the final, cleaned audio file from Cleanvoice
        local_final_path = os.path.join(temp_dir, f"processed_{os.path.basename(object_name)}")
        async with httpx.AsyncClient() as client:
            response = await client.get(processed_audio_url)
            with open(local_final_path, 'wb') as f:
                f.write(response.content)

        # 4. Upload the processed file back to your Spaces
        processed_object_name = object_name.replace("originals/", "processed/")
        final_upload_info = upload_processed_file_to_space(local_final_path, processed_object_name)

    # 5. Save the final result to the database
    record = Audio(
        user_id=user.id,
        file_path=final_upload_info["public_url"],
        object_name=final_upload_info["spaces_uri"],
        public_url=final_upload_info["public_url"],
    )
    db.add(record)
    db.commit()

    return {"message": "Audio processing complete!", "result": {"public_url": final_upload_info["public_url"]}}


@router.post("/process-video")
async def process_video(
        object_name: str = Body(..., embed=True),
        options: dict = Body(..., embed=True),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    """
    Processes a video file.
    Workflow: Download Video -> Extract Audio -> Upload Temp Audio -> Cleanvoice ->
              Download Processed Audio -> Recombine with Video -> Upload Final Video -> Save DB.
    """
    with TemporaryDirectory() as temp_dir:
        # 1. Download original video from Spaces
        original_video_local_path = os.path.join(temp_dir, os.path.basename(object_name))
        download_file_from_space(object_name, original_video_local_path)

        # 2. Extract its audio
        extracted_audio_local_path = extract_audio_from_video(original_video_local_path)

        # 3. Upload extracted audio to Spaces to get a temporary public URL
        temp_audio_object_name = f"users/{user.id}/temp/{os.path.basename(extracted_audio_local_path)}"
        temp_audio_info = upload_processed_file_to_space(extracted_audio_local_path, temp_audio_object_name)

        # 4. Process the temporary audio's URL via Cleanvoice
        print(f"Sending extracted audio {temp_audio_info['public_url']} to Cleanvoice...")
        processed_audio_url = await process_audio_from_url(temp_audio_info['public_url'], options)

        # 5. Download the final, cleaned audio from Cleanvoice
        processed_audio_local_path = os.path.join(temp_dir, "final_processed_audio.wav")
        async with httpx.AsyncClient() as client:
            response = await client.get(processed_audio_url)
            with open(processed_audio_local_path, 'wb') as f:
                f.write(response.content)

        # 6. Recombine the processed audio with the original video
        final_video_local_path = replace_audio_in_video(original_video_local_path, processed_audio_local_path)

        # 7. Upload the final processed video back to your Spaces
        processed_object_name = object_name.replace("originals/", "processed/")
        final_upload_info = upload_processed_file_to_space(final_video_local_path, processed_object_name)

    # 8. Save the final result to the database
    record = Video(
        user_id=user.id,
        file_path=final_upload_info["public_url"],
        object_name=final_upload_info["spaces_uri"],
        public_url=final_upload_info["public_url"],
    )
    db.add(record)
    db.commit()

    return {"message": "Video processing complete!", "result": {"public_url": final_upload_info["public_url"]}}