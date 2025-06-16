from fastapi import FastAPI
from src.video.router import router as video_router

app = FastAPI()

app.include_router(video_router)

