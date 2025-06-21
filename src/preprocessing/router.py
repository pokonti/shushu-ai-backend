from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pathlib import Path

from src.preprocessing.denoiser import denoise_audio
from src.preprocessing.service import find_video_file
from src.preprocessing.filler import (
    remove_filler_words_from_audio,
    remove_filler_words_from_video, get_filler_timestamps_from_audio, remove_filler_words_smooth,
)

router = APIRouter(prefix="/preprocessing", tags=["Preprocessing"])

UPLOAD_DIR = Path("video")
UPLOAD_DIR.mkdir(exist_ok=True)
AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)


# @router.post("/filler-words")
# def remove_filler_words(media_id: str, denoise: bool = False):
#     try:
#         audio_path = AUDIO_DIR / f"{media_id}.wav"
#         video_path = find_video_file(media_id, UPLOAD_DIR)
#
#         if not audio_path.exists():
#             raise HTTPException(status_code=404, detail="Audio file not found")
#
#         if denoise:
#             audio_path = Path(denoise_audio(str(audio_path)))
#
#         filler_times = get_filler_timestamps_from_audio(audio_path)
#
#         cleaned_audio_path = remove_filler_words_from_audio(str(audio_path), filler_times)
#
#
#         response = {
#             "message": "Filler words removed successfully",
#             "cleaned_audio": cleaned_audio_path,
#             "filler_timestamps": filler_times,
#         }
#
#         # Optionally remove filler words from video
#         if video_path.exists():
#             cleaned_video_path = remove_filler_words_from_video(str(video_path), filler_times)
#             response["cleaned_video"] = cleaned_video_path
#
#         return JSONResponse(content=response)
#
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/filler-words")
def remove_filler_words(media_id: str, denoise: bool = False):
    try:
        audio_path = AUDIO_DIR / f"{media_id}.wav"
        video_path = find_video_file(media_id, UPLOAD_DIR)

        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        if denoise:
            audio_path = Path(denoise_audio(str(audio_path)))

        filler_times = get_filler_timestamps_from_audio(audio_path)

        cleaned_audio_path = remove_filler_words_from_audio(str(audio_path), filler_times)


        response = {
            "message": "Filler words removed successfully",
            "cleaned_audio": cleaned_audio_path,
            "filler_timestamps": filler_times,
        }

        # Optionally remove filler words from video
        if video_path.exists():
            cleaned_video_path = remove_filler_words_smooth(str(video_path), filler_times)
            response["cleaned_video"] = cleaned_video_path

        return JSONResponse(content=response)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

