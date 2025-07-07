# attendtrack-110600-a2c40f8f

## Attendance Backend Setup & Run Instructions

### Install dependencies

```bash
cd attendance_backend
python3 -m venv .venv        # (optional but recommended)
source .venv/bin/activate    # (on Linux/Mac)
pip install -r requirements.txt
```

### Set environment variables

Create a `.env` file in `attendance_backend` with content like:
```
ATTENDANCE_DATABASE_URL=sqlite:///./attendance.db
AUTH_SECRET_KEY=changeme_please
```
Replace values as needed for your database.

### Run the backend

```bash
cd attendance_backend
chmod +x start.sh
./start.sh
```
The FastAPI server will be available at [http://localhost:8000](http://localhost:8000).

- For production: Remove `--reload` from `start.sh` and use a robust server setup.