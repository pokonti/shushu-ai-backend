import datetime
from src.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=True, unique=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=True)

    google_id = Column(String, unique=True, index=True, nullable=True)
    avatar_url = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    audios = relationship("Audio", back_populates="user", cascade="all, delete")
    videos = relationship("Video", back_populates="user", cascade="all, delete")
