import os
import json
from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from threading import Lock

# Load environment variables from .env file for secret key
load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_FILE = os.path.join(DATA_DIR, "attendance_data.json")

# Thread lock for concurrent file access
_json_lock = Lock()

def ensure_data_file():
    """Ensures that the data file exists and is initialized if necessary."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"users": [], "attendance": [], "user_counter": 1, "attendance_counter": 1}, f)
ensure_data_file()

# PUBLIC_INTERFACE
def read_data():
    """Safely loads user and attendance data from the JSON file."""
    with _json_lock:
        with open(DATA_FILE, "r") as f:
            return json.load(f)

# PUBLIC_INTERFACE
def write_data(data):
    """Safely writes user and attendance data to the JSON file."""
    with _json_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, default=str, indent=2)

# Authentication config
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "changeme_please")
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

# --- Pydantic Schemas ---

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
    username: str = Field(None, description="Username (subject)")

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

# --- Data Access Helper Functions ---

# PUBLIC_INTERFACE
def get_user_by_username(username: str) -> Optional[dict]:
    """Return the user dict by username, or None if not found."""
    data = read_data()
    for user in data["users"]:
        if user["username"] == username:
            return user
    return None

# PUBLIC_INTERFACE
def get_user_by_email(email: str) -> Optional[dict]:
    """Return the user dict by email, or None if not found."""
    data = read_data()
    for user in data["users"]:
        if user["email"] == email:
            return user
    return None

# PUBLIC_INTERFACE
def get_user_by_id(user_id: int) -> Optional[dict]:
    """Return the user dict by ID, or None if not found."""
    data = read_data()
    for user in data["users"]:
        if user["id"] == user_id:
            return user
    return None

# PUBLIC_INTERFACE
def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Verify user credentials; return user dict if successful, else None."""
    user = get_user_by_username(username)
    if user and verify_password(password, user["hashed_password"]):
        return user
    return None

# PUBLIC_INTERFACE
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency that gets current logged-in user from the Authorization Bearer JWT.
    """
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
    user = get_user_by_username(token_data.username)
    if user is None:
        raise credentials_exception
    return user

def user_to_userread(user: dict) -> UserRead:
    """Convert raw user dict to UserRead."""
    return UserRead(
        id=user["id"],
        username=user["username"],
        full_name=user["full_name"],
        email=user["email"],
    )

def attendance_to_read(record: dict) -> AttendanceRecordRead:
    """Convert raw attendance dict to AttendanceRecordRead."""
    return AttendanceRecordRead(
        id=record["id"],
        user_id=record["user_id"],
        status=record["status"],
        note=record.get("note"),
        timestamp=datetime.fromisoformat(record["timestamp"]),
    )

def get_latest_attendance_for_user(user_id: int) -> Optional[dict]:
    """Get the most recent attendance record for a user, if present."""
    data = read_data()
    records = [rec for rec in data["attendance"] if rec["user_id"] == user_id]
    if not records:
        return None
    return max(records, key=lambda rec: rec["timestamp"])

def add_user(user_data: UserCreate) -> dict:
    """Add new user; returns user dict."""
    data = read_data()
    user_id = data.get("user_counter", 1)
    hashed_pwd = get_password_hash(user_data.password)
    user_dict = {
        "id": user_id,
        "username": user_data.username,
        "full_name": user_data.full_name,
        "email": user_data.email,
        "hashed_password": hashed_pwd,
        "is_active": 1
    }
    data["users"].append(user_dict)
    data["user_counter"] = user_id + 1
    write_data(data)
    # Return without password hash
    ret = user_dict.copy()
    ret.pop("hashed_password")
    return user_dict

def add_attendance_record(user_id: int, status: str, note: Optional[str]) -> dict:
    """Add attendance record for user and return dict."""
    data = read_data()
    record_id = data.get("attendance_counter", 1)
    now_str = datetime.utcnow().isoformat()
    record_dict = {
        "id": record_id,
        "user_id": user_id,
        "status": status,
        "timestamp": now_str,
        "note": note,
    }
    data["attendance"].append(record_dict)
    data["attendance_counter"] = record_id + 1
    write_data(data)
    return record_dict

# -- FastAPI App and Routes --

app = FastAPI(
    title="Attendance Tracking API",
    description="FastAPI backend for attendance management, user authentication, and attendance records.",
    version="0.1.0",
    openapi_tags=[
        {"name": "Authentication", "description": "User registration, login, and profile."},
        {"name": "Attendance", "description": "Check-in and check-out attendance endpoints."}
    ]
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
):
    # Check for duplicate username or email
    if get_user_by_username(user.username) or get_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Username or email is already registered.")
    user_dict = add_user(user)
    return user_to_userread(user_dict)

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
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = {"sub": user["username"]}
    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get(
    "/me",
    response_model=UserRead,
    tags=["Authentication"],
    summary="Get current authenticated user details (JWT required)",
    description="Returns the profile of the currently authenticated user. Requires Bearer JWT in Authorization header.",
    responses={401: {"description": "Not authenticated."}},
)
def read_users_me(
    current_user: dict = Depends(get_current_user)
):
    return user_to_userread(current_user)

# -------------------- END AUTH ROUTES -------------------- #

# ------------------- ATTENDANCE ROUTES ------------------- #

@app.post(
    "/attendance/check-in",
    response_model=AttendanceRecordRead,
    tags=["Attendance"],
    summary="Mark attendance as check-in (requires JWT)",
    description="""
Record a check-in event for the authenticated user with the current UTC timestamp.
Prevents repeat check-ins without checking out. Requires valid Bearer JWT token.
""",
    responses={
        200: {"description": "Successfully checked in"},
        401: {"description": "Not authenticated"},
        409: {"description": "Already checked in (must check out first)"},
    }
)
# PUBLIC_INTERFACE
def check_in_attendance(
    note: Optional[str] = Body(None, description="Optional note"),
    current_user: dict = Depends(get_current_user),
):
    """
    Check in the logged-in user.
    - Requires JWT authentication.
    - Prevents check-in if user's latest attendance record is 'check-in' and no matching 'check-out'.
    """
    user_id = current_user["id"]
    latest_record = get_latest_attendance_for_user(user_id)
    if latest_record is not None and latest_record["status"] == "check-in":
        raise HTTPException(status_code=409, detail="User already checked in and not checked out.")
    record = add_attendance_record(
        user_id=user_id,
        status="check-in",
        note=note,
    )
    return attendance_to_read(record)

@app.post(
    "/attendance/check-out",
    response_model=AttendanceRecordRead,
    tags=["Attendance"],
    summary="Mark attendance as check-out (requires JWT)",
    description="""
Record a check-out event for the authenticated user with the current UTC timestamp.
User must check in first before checking out. Requires valid Bearer JWT token.
""",
    responses={
        200: {"description": "Successfully checked out"},
        401: {"description": "Not authenticated"},
        409: {"description": "User must check in before checking out"},
    }
)
# PUBLIC_INTERFACE
def check_out_attendance(
    note: Optional[str] = Body(None, description="Optional note"),
    current_user: dict = Depends(get_current_user),
):
    """
    Check out the logged-in user.
    - Requires JWT authentication.
    - Requires that user's latest attendance record is a 'check-in'.
    - Prevents check-out before check-in.
    """
    user_id = current_user["id"]
    latest_record = get_latest_attendance_for_user(user_id)
    if latest_record is None or latest_record["status"] != "check-in":
        raise HTTPException(status_code=409, detail="User must check in before checking out.")
    record = add_attendance_record(
        user_id=user_id,
        status="check-out",
        note=note,
    )
    return attendance_to_read(record)

# Optionally, add history/report endpoints here!

# No DB startup needed for file-based backend now
