from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from sqlalchemy.orm import Session
from src.auth import service, schemas
from src.auth.models import User
from src.auth.schemas import CreateUser
from src.auth.service import get_current_user, create_access_token
from src.database import get_db
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import requests
router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# This special value tells Google the code will be handled by JavaScript
GOOGLE_REDIRECT_URI = "postmessage"


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


@router.get("/profile")
def get_projects(current_user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    if db.query(User).filter(User.id == current_user.id).first():
        return current_user.audios, current_user.videos

@router.post("/google")
def auth_google(
        authorization_code: str = Body(..., embed=True, alias="code"),
        db: Session = Depends(get_db)
):
    """Handles the server-side part of the Google sign-in flow."""
    try:
        # 1. Exchange the authorization code for tokens.
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": authorization_code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        token_info = token_response.json()

        # 2. Verify the ID token to get user's info securely.
        id_info = id_token.verify_oauth2_token(
            token_info["id_token"], google_requests.Request(), GOOGLE_CLIENT_ID
        )

        google_user_id = id_info.get("sub")
        name = id_info.get("name")
        email = id_info.get("email")
        avatar = id_info.get("picture")

        # 3. Find or create the user in your database.
        user = db.query(User).filter(User.google_id == google_user_id).first()
        if not user:
            # User is new, create an account for them.
            user = User(email=email, google_id=google_user_id, username=name, avatar_url=avatar)
            db.add(user)
            db.commit()
            db.refresh(user)

        # 4. Issue your application's own JWT for this user.
        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google authentication failed: {str(e)}")
