from fastapi import FastAPI, Depends

from src.database import Base, engine, get_db
from typing import Annotated
from sqlalchemy.orm import Session
from src.media.router import router as video_router
from fastapi.middleware.cors import CORSMiddleware
from src.middleware.upload_limit import LimitUploadSizeMiddleware
from src.auth.router import router as auth_router
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LimitUploadSizeMiddleware, max_upload_size=3 * 1024**3) # 3 GB

# Base.metadata.drop_all(bind=engine)
Base.metadata.drop_all(bind=engine, checkfirst=True)
Base.metadata.create_all(bind=engine)

db_dependency = Annotated[Session, Depends(get_db)]
app.include_router(auth_router)
app.include_router(video_router)
# app.include_router(preprocessing_router)
