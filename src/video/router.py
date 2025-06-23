from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse

from src.preprocessing.denoiser import denoise_audio
from src.preprocessing.filler import get_filler_timestamps_from_audio, remove_filler_words_from_audio, \
    remove_filler_words_from_video, remove_filler_words_smooth
from src.preprocessing.service import find_video_file, transcribe_audio
from src.summary.service import get_summary
from src.video.service import save_uploaded_file, extract_audio_from_video, replace_audio_in_video

router = APIRouter(tags=["Basics"])

@router.post("/upload-audio")
async def upload_video(file: UploadFile = File(...),
                       denoise: bool = Query(False),
                       remove_fillers: bool = Query(False),
                       summarize: bool = Query(False)
                       ):
    if not file.filename.endswith((".mp3", ".wav")):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    file_info = save_uploaded_file(file)

    response_data = {
        "message": "Upload successful",
        "path":file_info["path"]
    }

    if denoise:
        try:
            denoised_path = denoise_audio(file_info["path"])
            response_data["path"] = denoised_path
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Denoise failed: {str(e)}")

    if remove_fillers:
        try:
            filler_times = get_filler_timestamps_from_audio(file_info["path"])
            cleaned_audio_path = remove_filler_words_from_audio(file_info["path"], filler_times)

            response_data.update({
                "path": cleaned_audio_path,
                "filler_timestamps": filler_times
            })

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Filler word removal failed: {str(e)}")

    if summarize:
        try:
            response_data["summary"] = get_summary(file_info["path"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

    return JSONResponse(content=response_data)

@router.post("/upload-video")
async def upload_video(file: UploadFile = File(...),
                       denoise: bool = Query(False),
                       remove_fillers: bool = Query(False),
                       summarize: bool = Query(False)
                       ):
    if not file.filename.endswith((".mp4", ".mov", ".mkv")):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    file_info = save_uploaded_file(file)

    try:
        audio_path = extract_audio_from_video(file_info["path"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")

    response_data = {
        "message": "Upload and audio extraction successful",
        "path":file_info["path"],
        "audio_path":audio_path
    }

    if denoise:
        try:
            denoised_path = denoise_audio(audio_path)
            response_data["audio_path"] = replace_audio_in_video(file_info["path"], denoised_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Denoise failed: {str(e)}")

    if remove_fillers:
        try:
            video_path = Path(file_info["path"])
            filler_times = get_filler_timestamps_from_audio(str(audio_path))
            cleaned_audio_path = remove_filler_words_from_audio(str(audio_path), filler_times)
            cleaned_video_path = remove_filler_words_smooth(str(video_path), filler_times)

            response_data.update({
                "audio_path": cleaned_audio_path,
                "cleaned_video":cleaned_video_path,
                "filler_timestamps": filler_times
            })

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Filler word removal failed: {str(e)}")

    if summarize:
        try:
            response_data["summary"] = get_summary(audio_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

    return JSONResponse(content=response_data)

