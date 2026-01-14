# University Voting System Backend

## Overview
A secure, FastAPI-based backend for a university voting system. Features include JWT authentication, Role-Based Access Control (Admin/User), and secure candidate/election management.

## Prerequisites
- Python 3.8+
- PostgreSQL database named `university_voting`.

## Setup

1.  **Configure Database**:
    -   Open `database.py`.
    -   Update `DB_PASSWORD` (and other fields if necessary) to match your local PostgreSQL credentials.

2.  **Install Dependencies**:
    ```bash
    pip install fastapi uvicorn psycopg2-binary python-jose[cryptography] passlib[bcrypt] python-multipart
    ```

3.  **Run the Server**:
    ```bash
    cd backend
    uvicorn main:app --reload
    ```
    -   API URL: `http://localhost:8000`
    -   Swagger Docs: `http://localhost:8000/docs`

## API Endpoints

### Authentication
-   **POST /register**: Register a new user.
    -   Body: `{ "username": "test", "email": "test@test.com", "password": "pass", "role": "user" }`
    -   *Note*: To create an admin, manually set `role` to `admin` in the database or during registration (if allowed).
-   **POST /token**: Login (OAuth2 standard).
    -   Form Data: `username` (use email), `password`.
-   **POST /login**: Login (JSON).
    -   Body: `{ "email": "...", "password": "..." }`

### Elections (Admin Write / Public Read)
-   **GET /elections**: List all elections.
-   **POST /elections**: Create an election (Admin only).

### Candidates (Admin Write / Public Read)
-   **GET /candidates**: List all candidates.
-   **POST /candidates**: Add a candidate (Admin only).
    -   Supports Base64 image uploads.
-   **DELETE /candidates/{id}**: Delete a candidate (Admin only).

### Voting (Authenticated Users)
-   **POST /vote**: Cast a vote.
    -   Headers: `Authorization: Bearer <token>`
    -   Body: `{ "candidate_id": 1 }`
    -   *Constraint*: Users can only vote once.

### Results
-   **GET /results**: Helper endpoint to view candidates sorted by votes.

## Security Features
-   **Password Hashing**: Uses Bcrypt.
-   **JWT Tokens**: Stateless authentication.
-   **RBAC**: Admin-only routes for sensitive operations.
