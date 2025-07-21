from fastapi import FastAPI, Depends
from src.database import Base, engine, get_db
from typing import Annotated
from sqlalchemy.orm import Session

from fastapi.middleware.cors import CORSMiddleware
from src.auth.router import router as auth_router
from src.space.router import router as space_router
from src.shorts.router import router as shorts_router
app = FastAPI()

origins = [
    "https://shushu.cam",
    "https://www.shushu.cam",
    "https://landing-demo-nine.vercel.app",
    "http://localhost:5173",

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base.metadata.drop_all(bind=engine)
# Base.metadata.drop_all(bind=engine, checkfirst=True)
Base.metadata.create_all(bind=engine)

db_dependency = Annotated[Session, Depends(get_db)]
app.include_router(auth_router)

# app.include_router(preprocessing_router)

# app.include_router(worker_router)
app.include_router(space_router)

app.include_router(shorts_router)

