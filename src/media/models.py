import datetime

from src.database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship



class Audio(Base):
    __tablename__ = "audios"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    object_name = Column(Text, nullable=False)
    public_url = Column(Text, nullable=True)

    status = Column(String, default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    summary = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="audios")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    object_name = Column(Text, nullable=False)
    public_url = Column(Text, nullable=True)

    status = Column(String, default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    summary = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="videos")
