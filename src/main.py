from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from src.video.router import router as video_router

app = FastAPI()

app.include_router(video_router)

