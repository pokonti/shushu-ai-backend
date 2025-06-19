from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from src.preprocessing.denoiser import denoise_audio
from src.video.service import save_uploaded_file, extract_audio_from_video, replace_audio_in_video

router = APIRouter()

router = APIRouter(tags=["Basics"])
@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename.endswith((".mp4", ".mov", ".mkv", ".mp3", ".wav")):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    file_info = save_uploaded_file(file)

    try:
        audio_path = extract_audio_from_video(file_info["path"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio extraction failed: {str(e)}")

    return JSONResponse(content={
        "message": "Upload and audio extraction successful",
        **file_info,
        "audio_path": audio_path
    })

