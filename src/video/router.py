from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse

from src.preprocessing.denoiser import denoise_audio
from src.preprocessing.filler import get_filler_timestamps_from_audio, remove_filler_words_from_audio, \
    remove_filler_words_from_video
from src.preprocessing.service import find_video_file
from src.video.service import save_uploaded_file, extract_audio_from_video, replace_audio_in_video

router = APIRouter(tags=["Basics"])

@router.post("/upload")
async def upload_video(file: UploadFile = File(...),
                       denoise: bool = Query(False),
                       remove_fillers: bool = Query(False),
                       summarize: bool = Query(False)
                       ):
    if not file.filename.endswith((".mp4", ".mov", ".mkv", ".mp3", ".wav")):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    file_info = save_uploaded_file(file)

    try:
        audio_path = extract_audio_from_video(file_info["path"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")

    response_data = {
        "message": "Upload and audio extraction successful",
        **file_info,
        "audio_path": audio_path
    }

    if denoise:
        denoised_path = denoise_audio(audio_path)
        response_data["audio_path"] = denoised_path

    if remove_fillers:
        try:
            video_path = Path(file_info["path"])
            filler_times = get_filler_timestamps_from_audio(str(audio_path))
            cleaned_audio_path = remove_filler_words_from_audio(str(audio_path), filler_times)

            response_data.update({
                "cleaned_audio": cleaned_audio_path,
                "filler_timestamps": filler_times
            })

            if video_path and video_path.exists():
                cleaned_video_path = remove_filler_words_from_video(str(video_path), filler_times)
                response_data["cleaned_video"] = cleaned_video_path

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Filler word removal failed: {str(e)}")

    return JSONResponse(content=response_data)

