from fastapi import APIRouter

router = APIRouter()

@router.post("/summarize/")
def summarize_audio(filename: str):
    # Stub for future implementation
    return {"message": "Coming soon: audio/video summarization"}