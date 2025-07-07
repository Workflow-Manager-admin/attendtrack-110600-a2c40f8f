import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file for DB connection
load_dotenv()

# PUBLIC_INTERFACE
def get_database_url():
    """Get the database URL from environment variables for SQLAlchemy connection."""
    # Reference to attendance_database connection string
    db_url = os.getenv("ATTENDANCE_DATABASE_URL")
    if db_url is None:
        raise RuntimeError("ATTENDANCE_DATABASE_URL not set in environment")
    return db_url

SQLALCHEMY_DATABASE_URL = get_database_url()

# SQLAlchemy setup
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models

# PUBLIC_INTERFACE
class User(Base):
    """Database model representing a user of the attendance system."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Integer, default=1)
    # Relationship to attendance records
    attendance_records = relationship("AttendanceRecord", back_populates="user")

# PUBLIC_INTERFACE
class AttendanceRecord(Base):
    """Database model representing an attendance record entry."""
    __tablename__ = "attendance_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False)  # e.g. "check-in", "check-out"
    note = Column(String, nullable=True)

    user = relationship("User", back_populates="attendance_records")


# Pydantic Schemas

# PUBLIC_INTERFACE
class UserBase(BaseModel):
    """Base schema for user information."""
    username: str = Field(..., description="Unique username for the user")
    full_name: str = Field(..., description="Full name of the user")
    email: str = Field(..., description="Email address")

# PUBLIC_INTERFACE
class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., description="Password for the user")

# PUBLIC_INTERFACE
class UserRead(UserBase):
    """Schema for responding with user information."""
    id: int

    class Config:
        from_attributes = True

# PUBLIC_INTERFACE
class AttendanceRecordBase(BaseModel):
    """Base schema for attendance record information."""
    status: str = Field(..., description="Attendance status ('check-in' or 'check-out')")
    note: Optional[str] = Field(None, description="Optional note for the attendance record")

# PUBLIC_INTERFACE
class AttendanceRecordCreate(AttendanceRecordBase):
    """Schema for creating a new attendance record."""
    pass

# PUBLIC_INTERFACE
class AttendanceRecordRead(AttendanceRecordBase):
    """Schema for responding with attendance record information."""
    id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# Dependency for FastAPI routes

# PUBLIC_INTERFACE
def get_db():
    """Yield a database session to be used in FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(
    title="Attendance Tracking API",
    description="FastAPI backend for attendance management, user authentication, and attendance records.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    """Health check endpoint for service status."""
    return {"message": "Healthy"}

# Initial migration logic (creates tables on startup if not present)
@app.on_event("startup")
def on_startup():
    """Create database tables if they do not exist, resembling a simple migration."""
    Base.metadata.create_all(bind=engine)
