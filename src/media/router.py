from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path

from src.auth.models import User
from src.media.models import Video, Audio
from src.auth.service import get_current_user
from src.database import get_db
# from src.preprocessing.denoiser import denoise_audio
from src.preprocessing.filler import get_filler_timestamps_from_audio, remove_filler_words_from_audio, remove_filler_words_smooth
from src.summary.service import get_summary
from src.media.service import save_uploaded_file, extract_audio_from_video, replace_audio_in_video

router = APIRouter(tags=["Basics"])


# @router.post("/denoise/")
# async def denoise(file: UploadFile = File(...)):
#     try:
#         with NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
#             temp_file.write(await file.read())
#             temp_path = temp_file.name
#
#         # Upload to Cleanvoice
#         uploaded_file_id = await upload_file_to_cleanvoice(temp_path, file.filename)
#
#         # Request noise removal
#         task = await request_denoising(uploaded_file_id)
#
#         return {
#             "status": "submitted",
#             "cleanvoice_task": task
#         }
#
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

# @router.post("/upload-audio")
# async def upload_video(file: UploadFile = File(...),
#                        denoise: bool = Query(False),
#                        remove_fillers: bool = Query(False),
#                        summarize: bool = Query(False),
#                        db: Session = Depends(get_db),
#                        user: User = Depends(get_current_user)
#                        ):
#     if not file.filename.endswith((".mp3", ".wav")):
#         raise HTTPException(status_code=400, detail="Unsupported file format")
#
#     file_info = save_uploaded_file(file)
#
#     response_data = {
#         "message": "Upload successful",
#         "path":file_info["path"]
#     }
#
#     if denoise:
#         try:
#             denoised_path = denoise_audio(file_info["path"])
#             response_data["path"] = denoised_path
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Denoise failed: {str(e)}")
#
#     if remove_fillers:
#         try:
#             filler_times = get_filler_timestamps_from_audio(file_info["path"])
#             cleaned_audio_path = remove_filler_words_from_audio(file_info["path"], filler_times)
#
#             response_data.update({
#                 "path": cleaned_audio_path,
#                 "filler_timestamps": filler_times
#             })
#
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Filler word removal failed: {str(e)}")
#
#     if summarize:
#         try:
#             response_data["summary"] = get_summary(file_info["path"])
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")
#
#     audio = Audio(user_id=user.id, file_path=response_data["path"], gcs_uri=gcs_uri, public_url=public_url)
#     db.add(audio)
#     db.commit()
#     db.refresh(audio)
#
#     response_data["db"] = "saved"
#     return JSONResponse(content=response_data)
#
# @router.post("/upload-video")
# async def upload_video(file: UploadFile = File(...),
#                        denoise: bool = Query(False),
#                        remove_fillers: bool = Query(False),
#                        summarize: bool = Query(False),
#                        db: Session = Depends(get_db),
#                        user: User = Depends(get_current_user)
#                        ):
#     if not file.filename.endswith((".mp4", ".mov", ".mkv")):
#         raise HTTPException(status_code=400, detail="Unsupported file format")
#
#     file_info = save_uploaded_file(file)
#
#     try:
#         audio_path = extract_audio_from_video(file_info["path"])
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")
#
#     response_data = {
#         "message": "Upload and audio extraction successful",
#         "path":file_info["path"],
#         "audio_path":audio_path
#     }
#
#     if denoise:
#         try:
#             denoised_path = denoise_audio(audio_path)
#             response_data["audio_path"] = replace_audio_in_video(file_info["path"], denoised_path)
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Denoise failed: {str(e)}")
#
#     if remove_fillers:
#         try:
#             video_path = Path(file_info["path"])
#             filler_times = get_filler_timestamps_from_audio(str(audio_path))
#             cleaned_audio_path = remove_filler_words_from_audio(str(audio_path), filler_times)
#             cleaned_video_path = remove_filler_words_smooth(str(video_path), filler_times)
#
#             response_data.update({
#                 "audio_path": cleaned_audio_path,
#                 "cleaned_video":cleaned_video_path,
#                 "filler_timestamps": filler_times
#             })
#
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Filler word removal failed: {str(e)}")
#
#     if summarize:
#         try:
#             response_data["summary"] = get_summary(audio_path)
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")
#
#     public_url, gcs_uri = upload_to_gcs(file, user.id, False)
#     response_data["public_url"] = public_url
#     response_data["gcs_uri"] = gcs_uri
#
#     video = Video(user_id=user.id, file_path=response_data["path"], gcs_uri=gcs_uri, public_url=public_url)
#     db.add(video)
#     db.commit()
#     db.refresh(video)
#
#     response_data["db"]="saved"
#     return JSONResponse(content=response_data)
#
# @router.post("/update-processed-audio/{audio_id}")
# async def update_processed_audio(
#     audio_id: int,
#     processed_gcs_uri: str,
#     processed_public_url: str,
#     db: Session = Depends(get_db),
#     user: User = Depends(get_current_user)
# ):
#     """Update the Audio DB record with processed file info after Celery task completes."""
#     audio = db.query(Audio).filter(Audio.id == audio_id, Audio.user_id == user.id).first()
#     if not audio:
#         raise HTTPException(status_code=404, detail="Audio file not found")
#     audio.file_path = processed_public_url
#     audio.gcs_uri = processed_gcs_uri
#     db.commit()
#     db.refresh(audio)
#     return {"message": "Audio updated", "audio_id": audio_id}
#
# @router.post("/update-processed-video/{video_id}")
# async def update_processed_video(
#     video_id: int,
#     processed_gcs_uri: str,
#     processed_public_url: str,
#     db: Session = Depends(get_db),
#     user: User = Depends(get_current_user)
# ):
#     """Update the Video DB record with processed file info after Celery task completes."""
#     video = db.query(Video).filter(Video.id == video_id, Video.user_id == user.id).first()
#     if not video:
#         raise HTTPException(status_code=404, detail="Video file not found")
#     video.file_path = processed_public_url
#     video.gcs_uri = processed_gcs_uri
#     db.commit()
#     db.refresh(video)
#     return {"message": "Video updated", "video_id": video_id}
#
