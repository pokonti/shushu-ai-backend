from fastapi import FastAPI
from src.video.router import router as video_router
from src.preprocessing.router import router as preprocessing_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(video_router)
app.include_router(preprocessing_router)
