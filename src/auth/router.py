from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from sqlalchemy.orm import Session
from src.auth import service, schemas
from src.auth.models import User
from src.auth.schemas import CreateUser
from src.auth.service import get_current_user
from src.database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)
@router.post("/register")
def register(user: CreateUser, db: Session = Depends(get_db)):
    service.register(user, db)
    return {"ok": True}


@router.post("/login", response_model=schemas.Token)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    access_token = service.login(form_data, db)
    return schemas.Token(access_token=access_token, token_type="bearer")

@router.get("/me")
def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return service.read_users_me(current_user)