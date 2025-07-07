import os
from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

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

# --- Authentication Config & Utility Functions ---

SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "changeme_please")  # Replace in .env in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# PUBLIC_INTERFACE
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

# PUBLIC_INTERFACE
def get_password_hash(password: str) -> str:
    """Generate a hashed password from a plaintext password."""
    return pwd_context.hash(password)

# PUBLIC_INTERFACE
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token for the given payload data."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# PUBLIC_INTERFACE
def decode_access_token(token: str) -> dict:
    """Decode a JWT access token and return the payload if valid, else raise exception."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials (invalid or expired token)",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
class UserLogin(BaseModel):
    """Schema for user login request."""
    username: str = Field(..., description="The username for login")
    password: str = Field(..., description="The password for login")

# PUBLIC_INTERFACE
class UserRead(UserBase):
    """Schema for responding with user information."""
    id: int

    class Config:
        from_attributes = True

# PUBLIC_INTERFACE
class Token(BaseModel):
    """Schema for JWT access token response."""
    access_token: str = Field(..., description="JWT Bearer token")
    token_type: str = Field(..., description="Authentication token type")

# PUBLIC_INTERFACE
class TokenData(BaseModel):
    """Structured user data from JWT token after decoding."""
    username: str = Field(..., description="Username (subject)", default=None)

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

# --- Authentication Route Dependencies & Logic ---

# PUBLIC_INTERFACE
def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Return a User by username if exists, else None."""
    return db.query(User).filter(User.username == username).first()

# PUBLIC_INTERFACE
def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Verify user credentials; return User if successful, else None."""
    user = get_user_by_username(db, username=username)
    if user and verify_password(password, user.hashed_password):
        return user
    return None

# PUBLIC_INTERFACE
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency that gets current logged-in user from the Authorization Bearer JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials (token missing/invalid)",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

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

# ------------------------ AUTH ROUTES ------------------------ #

@app.post(
    "/register",
    response_model=UserRead,
    status_code=201,
    tags=["Authentication"],
    summary="Register a new user account",
    description="""
Register a new user by providing a unique username, email, full name, and password.

- Password is securely hashed and not returned.
- If username or email is already registered, 409 is returned.
    """,
    responses={
        201: {"description": "Successfully registered, returns created user (excluding password)"},
        409: {"description": "User with username or email already exists"},
    }
)
# PUBLIC_INTERFACE
def register_user(
    user: UserCreate = Body(..., description="User registration data"),
    db: Session = Depends(get_db),
):
    # Check for duplicate username or email
    duplicate_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if duplicate_user:
        raise HTTPException(status_code=409, detail="Username or email is already registered.")
    # Hash password and create new user
    hashed_pwd = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_pwd,
        is_active=1
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post(
    "/login",
    response_model=Token,
    tags=["Authentication"],
    summary="Login and obtain JWT Bearer token",
    description="""
Authenticate a registered user and obtain a JWT access token for API access.

- On success, returns a JWT Bearer token.
- On failure (invalid credentials), returns HTTP 401.
    """,
    responses={
        200: {"description": "Successfully authenticated, returns access token"},
        401: {"description": "Invalid credentials"},
    },
)
# PUBLIC_INTERFACE
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Generate JWT token with user identification
    token_data = {"sub": user.username}
    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}

# Example: protected endpoint (shows how to use get_current_user dependency)
@app.get(
    "/me",
    response_model=UserRead,
    tags=["Authentication"],
    summary="Get current authenticated user details (JWT required)",
    description="Returns the profile of the currently authenticated user. Requires Bearer JWT in Authorization header.",
    responses={401: {"description": "Not authenticated."}},
)
def read_users_me(
    current_user: User = Depends(get_current_user)
):
    return current_user

# -------------------- END AUTH ROUTES -------------------- #
