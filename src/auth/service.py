from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, APIRouter
from passlib.context import CryptContext
from typing import Annotated
from sqlalchemy.orm import Session
from src.auth.models import User
from src.auth.schemas import CreateUser
from src.database import get_db
from dotenv import load_dotenv
import os

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES)))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: Annotated[str, Depends(oauth2_bearer)], db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise credentials_exception
    return user

def register(user: CreateUser, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=user.email).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    new_user = User(email=user.email,
                    username=user.username,
                    hashed_password=hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token({"sub": user.email})
    return access_token

def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return {"id": current_user.id, "username": current_user.username, "email": current_user.email}