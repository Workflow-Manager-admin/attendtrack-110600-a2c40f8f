# Attendance Backend REST API Documentation

This document describes the REST API endpoints for the `attendance_backend`, a FastAPI application that manages user authentication and attendance check-in/check-out.

> **Note:**  
> At the time of documenting, **there are no endpoints implemented for attendance history viewing, report export/download, or dashboard summary**. Endpoints currently only support authentication (registration, login, get-profile) and attendance check-in/check-out.

---

## Authentication Endpoints

### Register a New User

- **Endpoint:** `POST /register`
- **Description:** Register a new user account.
- **Request Body (application/json):**
  ```json
  {
    "username": "janedoe",
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "password": "secure_password"
  }
  ```
- **Responses:**
  - `201 Created`  
    Returns the created user (without password).
    ```json
    {
      "id": 1,
      "username": "janedoe",
      "full_name": "Jane Doe",
      "email": "jane@example.com"
    }
    ```
  - `409 Conflict`  
    Username or email is already registered.
    ```json
    { "detail": "Username or email is already registered." }
    ```

---

### User Login

- **Endpoint:** `POST /login`
- **Description:** Log in a user and get a JWT Bearer token.
- **Request Body (application/x-www-form-urlencoded):**
  ```
  username=janedoe&password=secure_password
  ```
- **Responses:**
  - `200 OK`  
    ```json
    {
      "access_token": "JWT_TOKEN_STRING",
      "token_type": "bearer"
    }
    ```
  - `401 Unauthorized`
    ```json
    {
      "detail": "Incorrect username or password"
    }
    ```

---

### Get Current User Profile

- **Endpoint:** `GET /me`
- **Description:** Get user information of the currently authenticated user.  
- **Headers:**  
  `Authorization: Bearer <JWT_TOKEN_STRING>`
- **Responses:**
  - `200 OK`
    ```json
    {
      "id": 1,
      "username": "janedoe",
      "full_name": "Jane Doe",
      "email": "jane@example.com"
    }
    ```
  - `401 Unauthorized`
    ```json
    { "detail": "Could not validate credentials (token missing/invalid)" }
    ```

---

## Attendance Endpoints

### Check-In

- **Endpoint:** `POST /attendance/check-in`
- **Description:** Mark the authenticated user as checked in.  
  User must not already be checked in (must check out before next check-in).
- **Headers:**  
  `Authorization: Bearer <JWT_TOKEN_STRING>`
- **Request Body (application/json):**
  ```json
  {
    "note": "Arriving for work"
  }
  ```
  (The `note` field is optional.)
- **Responses:**
  - `200 OK`
    ```json
    {
      "id": 10,
      "user_id": 1,
      "status": "check-in",
      "timestamp": "2024-06-15T08:00:01.123456",
      "note": "Arriving for work"
    }
    ```
  - `401 Unauthorized`
    ```json
    { "detail": "Could not validate credentials (token missing/invalid)" }
    ```
  - `409 Conflict`
    ```json
    { "detail": "User already checked in and not checked out." }
    ```

---

### Check-Out

- **Endpoint:** `POST /attendance/check-out`
- **Description:** Mark the authenticated user as checked out.  
  User must have checked in before checking out.
- **Headers:**  
  `Authorization: Bearer <JWT_TOKEN_STRING>`
- **Request Body (application/json):**
  ```json
  {
    "note": "Leaving for the day"
  }
  ```
  (The `note` field is optional.)
- **Responses:**
  - `200 OK`
    ```json
    {
      "id": 11,
      "user_id": 1,
      "status": "check-out",
      "timestamp": "2024-06-15T17:01:11.654321",
      "note": "Leaving for the day"
    }
    ```
  - `401 Unauthorized`
    ```json
    { "detail": "Could not validate credentials (token missing/invalid)" }
    ```
  - `409 Conflict`
    ```json
    { "detail": "User must check in before checking out." }
    ```

---

## Health Check

- **Endpoint:** `GET /`
- **Description:** Simple health check endpoint.  
- **Response:**
  - `200 OK`
    ```json
    { "message": "Healthy" }
    ```

---

## Models & Schemas

### User Fields

| Field      | Type     | Description          |
|------------|----------|----------------------|
| id         | integer  | User ID (response)   |
| username   | string   | Unique username      |
| full_name  | string   | Full name            |
| email      | string   | Email address        |
| password   | string   | (request only) User password |

### Attendance Record Fields

| Field      | Type     | Description                        |
|------------|----------|------------------------------------|
| id         | integer  | Record ID (response only)          |
| user_id    | integer  | User ID                            |
| status     | string   | "check-in" or "check-out"          |
| timestamp  | string   | Date and time in UTC (ISO format)  |
| note       | string?  | Optional remarks                   |

---

## Overview (Current API Features & Limitations)

- User registration, login, and get-profile are supported.
- Attendance check-in/check-out is supported **per user and per session**.
- All attendance actions are protected and require providing a valid JWT Bearer token.
- **Not yet implemented:**  
  - Endpoints to view attendance history (for a given user or date range)
  - Export or download (CSV, Excel, PDF) of attendance records or reports
  - Dashboard endpoints summarizing attendance statistics

---

## Security

- JWT Bearer tokens (`Authorization: Bearer ...`) are required for all attendance endpoints and protected profile endpoints.
- All passwords are always hashed (bcrypt) on storage.
- CORS is set to allow all origins (not recommended for production).

---

## Example Usage Flow

1. **Register** user via `/register`.
2. **Login** via `/login` to get JWT token.
3. Include `Authorization: Bearer <token>` in subsequent requests.
4. Use `/attendance/check-in` and `/attendance/check-out` to submit attendance events.
5. Get profile with `/me`.

---

## Future Improvements (Needed for Full Feature Support)

- Implement endpoints for:
  - Attendance history retrieval (`GET /attendance/history`)
  - Report export/download (`GET /attendance/export`)
  - Attendance summary/dashboard (`GET /dashboard/summary`)

---

## Mermaid Diagram – Endpoint Map

```mermaid
graph TD
    A[POST /register<br/>Register User] -->|returns user| B((User))
    C[POST /login<br/>Login (returns JWT)] -.-> D((Token))
    D -.->|JWT Bearer| B
    E[GET /me<br/>Get User Profile] -- JWT --> B
    F[POST /attendance/check-in<br/>Check-In] -- JWT --> G((Attendance Record))
    H[POST /attendance/check-out<br/>Check-Out] -- JWT --> G
    I[GET /<br/>Health Check] --> J((Service Status))
```

---

## References

- See source: [`attendance_backend/src/api/main.py`](../attendance_backend/src/api/main.py)
