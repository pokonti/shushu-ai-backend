from pydantic import BaseModel, EmailStr


class CreateUser(BaseModel):
    username: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str