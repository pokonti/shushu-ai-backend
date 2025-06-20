from fastapi import APIRouter

router = APIRouter()

@router.post("/summarize/")
def summarize_audio(filename: str):
    
    return {"message": "Coming soon: audio/video summarization"}