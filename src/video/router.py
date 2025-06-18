from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from src.preprocessing.denoiser import denoise_audio
from src.video.service import save_uploaded_file, extract_audio_from_video, replace_audio_in_video

router = APIRouter()

@router.post("/upload/")
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



@router.get("/new")
def get_new_video():
    try:
        audio_filename = "audio/e356ae92-f97a-4a77-84d5-46a1a3e24e64_enhanced.wav"
        video_filename = "uploads/e356ae92-f97a-4a77-84d5-46a1a3e24e64.mp4"

        output_path = replace_audio_in_video(video_filename, audio_filename)
        return {"message": "Video created", "output": output_path}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})



# @router.post("/generate-short-clip/")
# def generate_short_clip(filename: str):
#     # Stub for future implementation
#     return {"message": "Coming soon: short video clip generation"}

@router.post("/summarize/")
def summarize_audio(filename: str):
    # Stub for future implementation
    return {"message": "Coming soon: audio/video summarization"}