from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path

from src.preprocessing.denoiser import denoise_audio
from src.preprocessing.service import transcribe_audio
from src.preprocessing.filler import (
    get_filler_word_timestamps,
    remove_filler_words_from_audio,
    remove_filler_words_from_video, align_transcripts,
)

router = APIRouter(prefix="/preprocessing", tags=["Preprocessing"])

@router.get("/denoise")
def run_denoising():
    try:
        filename = "audio/4f7d9ee0-a077-4b2c-90d9-40f4cad12f3a.wav"
        output_path = denoise_audio(filename)
        return JSONResponse(content={
            "message": "Denoising successful",
            "output_path": output_path
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/filler-words")
def remove_filler_words():
    try:
        audio_path = f"audio/4f7d9ee0-a077-4b2c-90d9-40f4cad12f3a.wav"
        video_path = f"uploads/4f7d9ee0-a077-4b2c-90d9-40f4cad12f3a.mov"

        if not Path(audio_path).exists() or not Path(video_path).exists():
            raise HTTPException(status_code=404, detail="Audio or video file not found")

        # Step 1: Transcribe
        # transcription = transcribe_audio(audio_path)
        # if "error" in transcription:
        #     raise HTTPException(status_code=500, detail="Transcription failed")

        # Step 2: Get filler timestamps
        # filler_times = get_filler_word_timestamps(transcription["words"])
        base = transcribe_audio(audio_path, model_size="base")
        medium = transcribe_audio(audio_path, model_size="medium")

        filler_times = align_transcripts(base["words"], medium["words"])
        print(base["words"])
        print(medium["words"])
        print(filler_times)
        filler_times = get_filler_word_timestamps(filler_times)

        # Step 3: Remove from audio and video
        cleaned_audio_path = remove_filler_words_from_audio(audio_path, filler_times)
        cleaned_video_path = remove_filler_words_from_video(video_path, filler_times)

        return JSONResponse(content={
            "message": "Filler words removed successfully",
            "cleaned_audio": cleaned_audio_path,
            "cleaned_video": cleaned_video_path,
            "filler_timestamps": filler_times
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
