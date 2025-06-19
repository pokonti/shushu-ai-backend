from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pathlib import Path

from src.preprocessing.denoiser import denoise_audio
from src.preprocessing.service import transcribe_audio, find_video_file
from src.preprocessing.filler import (
    get_filler_word_timestamps,
    remove_filler_words_from_audio,
    remove_filler_words_from_video, align_transcripts, get_filler_timestamps_from_audio,
)
from src.video.service import replace_audio_in_video

router = APIRouter(prefix="/preprocessing", tags=["Preprocessing"])

UPLOAD_DIR = Path("video")
UPLOAD_DIR.mkdir(exist_ok=True)
AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)

# @router.get("/denoise")
# def run_denoising(media_id: str):
#     audio_path = AUDIO_DIR / f"{media_id}.wav"
#     video_path = find_video_file(media_id, UPLOAD_DIR)
#
#     try:
#         if audio_path.exists():
#             output_path = denoise_audio(str(audio_path))
#             return JSONResponse(content={
#                 "message": "Audio denoised successfully",
#                 "output_path": output_path
#             })
#
#         if video_path.exists():
#             enhanced_video = replace_audio_in_video(str(video_path), f"{AUDIO_DIR}/{media_id}_cleaned.wav")
#
#             return JSONResponse(content={
#                 "message": "Video denoised successfully",
#                 "output_path": enhanced_video
#             })
#
#         else:
#             raise HTTPException(status_code=400, detail="You must provide either audio_path or video_path.")
#
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/denoise")
def run_denoising(media_id: str):
    try:
        audio_path = AUDIO_DIR / f"{media_id}.wav"
        video_path = find_video_file(media_id, UPLOAD_DIR)

        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        output_path = denoise_audio(str(audio_path))

        if video_path and video_path.exists():
            enhanced_audio_path = AUDIO_DIR / f"{media_id}_denoised.wav"
            enhanced_video = replace_audio_in_video(str(video_path), str(enhanced_audio_path))

            return JSONResponse(content={
                "message": "Video denoised successfully",
                "output_path": enhanced_video
            })

        return JSONResponse(content={
            "message": "Audio denoised successfully",
            "output_path": output_path
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


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
        # cleaned_audio_path = remove_filler_words_from_audio_smooth(str(audio_path), filler_times)


        response = {
            "message": "Filler words removed successfully",
            "cleaned_audio": cleaned_audio_path,
            "filler_timestamps": filler_times,
        }

        # Optionally remove filler words from video
        if video_path.exists():
            cleaned_video_path = remove_filler_words_from_video(str(video_path), filler_times)
            response["cleaned_video"] = cleaned_video_path

        return JSONResponse(content=response)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})



