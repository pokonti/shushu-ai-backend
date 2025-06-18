from fastapi import FastAPI
from src.video.router import router as video_router
from src.preprocessing.router import router as preprocessing_router
app = FastAPI()

app.include_router(video_router)
app.include_router(preprocessing_router)
