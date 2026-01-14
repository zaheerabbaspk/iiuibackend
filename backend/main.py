from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from typing import List, Optional, Union
import base64
import uuid
import os
import psycopg2
import hashlib
from jose import JWTError, jwt
from passlib.context import CryptContext
import random
import string

# Import local modules
from database import get_db_connection, init_db
from models import (
    UserRegister, UserLogin, UserResponse,
    Token, TokenData,
    CandidateCreate, CandidateResponse,
    ElectionCreate, ElectionUpdate, ElectionResponse,
    VoteRequest, TokenGenerateRequest, VotingTokenResponse, TokenLoginRequest, TokenAddRequest
)

# --- Configuration ---
SECRET_KEY = "your-very-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(title="University Voting System API")

# CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static# Constants
import socket
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

LOCAL_IP = get_ip()
BASE_URL = f"http://{LOCAL_IP}:8000"
print(f"--- SERVER INFO ---")
print(f"Local IP: {LOCAL_IP}")
print(f"Base URL: {BASE_URL}")
print(f"-------------------")
# Use absolute path for uploads to avoid confusion
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads")

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
    print(f"Created uploads directory at: {UPLOAD_DIR}")

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.on_event("startup")
def startup_event():
    init_db()

# --- Helper Functions ---

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email, role=role)
    except JWTError:
        raise credentials_exception
        
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="Database connection failed")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (token_data.email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user is None:
        raise credentials_exception
    return user

def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

def throw_db_error(e=None):
    if e: print(f"DB Error: {e}")
    raise HTTPException(status_code=500, detail="Database connection failed")

# --- Auth Endpoints ---

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserRegister):
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        hashed_pw = get_password_hash(user.password)
        cur.execute(
            """
            INSERT INTO users (username, email, password, role, has_voted)
            VALUES (%s, %s, %s, %s, FALSE)
            RETURNING id, username, email, role, has_voted
            """,
            (user.username, user.email, hashed_pw, user.role)
        )
        new_user = cur.fetchone()
        conn.commit()
        return new_user
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

# Compatible with OAuth2 standard form (username, password)
@app.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    # OAuth2 spec uses 'username' field, but we treat it as email
    cur.execute("SELECT * FROM users WHERE email = %s", (form_data.username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['email'], "role": user['role']}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user['role']}

@app.post("/login", response_model=Token)
def login_json(user_login: UserLogin):
    """JSON body login endpoint for generic frontend usage"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = %s", (user_login.email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(user_login.password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['email'], "role": user['role']}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user['role']}

@app.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

# --- Election Endpoints (Public Read, Admin Write) ---

@app.get("/elections", response_model=List[ElectionResponse])
def get_elections(token: Optional[str] = None):
    """Sare elections ya filter by token (Voter authorized list)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        if token:
            token_str = token.strip().upper()
            cur.execute("""
                SELECT e.* 
                FROM elections e
                JOIN token_elections te ON (e.id::text = te.election_id OR e.name = te.election_id)
                JOIN voting_tokens vt ON te.token_id = vt.id
                WHERE vt.token = %s
                ORDER BY e.created_at DESC
            """, (token_str,))
        else:
            cur.execute("SELECT * FROM elections ORDER BY created_at DESC")
            
        results = cur.fetchall()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/elections", response_model=ElectionResponse, status_code=status.HTTP_201_CREATED)
def create_election(election: ElectionCreate):
    """API for adding a new election (Security Removed)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO elections (name, description, start_date, end_date, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (election.name, election.description, election.start_date, election.end_date, election.status)
        )
        new_election = cur.fetchone()
        conn.commit()
        return new_election
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.put("/elections/{id}", response_model=ElectionResponse)
def update_election(id: int, election: ElectionUpdate):
    """Admin calls this to edit election details"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # Build dynamic update query
        update_data = election.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No data provided to update")
            
        set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
        values = list(update_data.values())
        values.append(id)
        
        cur.execute(f"UPDATE elections SET {set_clause} WHERE id = %s RETURNING *", values)
        updated = cur.fetchone()
        conn.commit()
        if not updated:
            raise HTTPException(status_code=404, detail="Election not found")
        return updated
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.patch("/elections/{id}/status")
def update_election_status(id: int, status: str):
    """Admin: Start, Pause, or End an election (Status Control)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # Validate status
        valid_statuses = ["draft", "active", "ended", "paused"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        cur.execute(
            "UPDATE elections SET status = %s WHERE id = %s RETURNING *",
            (status, id)
        )
        updated = cur.fetchone()
        
        if not updated:
            raise HTTPException(status_code=404, detail="Election not found")
        
        conn.commit()
        return {
            "status": "success",
            "election": updated,
            "message": f"Election status changed to: {status}"
        }
    except HTTPException as he:
        conn.rollback()
        raise he
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.delete("/elections/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_election(id: int):
    """Admin calls this to delete an election"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM elections WHERE id = %s RETURNING id", (id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Election not found")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/elections/{id}", response_model=ElectionResponse)
def get_election_by_id(id: Union[int, str]):
    """Sari details ek specific election ki (ID ke zariye)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    # Handle int or str ID
    if str(id).isdigit():
        cur.execute("SELECT * FROM elections WHERE id = %s", (int(id),))
    else:
        # If they use a string code, we might need a separate column or just check name?
        # For now, let's keep it consistent with the user's intent
        cur.execute("SELECT * FROM elections WHERE name = %s", (str(id),))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    if not result:
        raise HTTPException(status_code=404, detail="Election not found")
    return result

@app.get("/elections/{id}/candidates", response_model=List[CandidateResponse])
def get_election_candidates(id: str):
    """Ek specific election ke sare candidates (Admin/User app link karne ke liye)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    cur.execute("SELECT id, name, position, party, election_id, image_url, vote_count, image_url as image FROM candidates WHERE election_id = %s", (id,))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

# --- Candidates Endpoints (Public Read, Admin Write) ---

@app.get("/candidates", response_model=List[CandidateResponse])
def get_candidates(token: Optional[str] = None):
    """Sare candidates ya filter by token (Sari details ke saath)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        if token:
            token_str = token.strip().upper()
            # 1. Pehle token ke authorized election IDs nikalen
            cur.execute("""
                SELECT te.election_id 
                FROM token_elections te
                JOIN voting_tokens vt ON te.token_id = vt.id
                WHERE vt.token = %s
            """, (token_str,))
            rows = cur.fetchall()
            election_ids = [r['election_id'] for r in rows]
            
            if not election_ids:
                return []
            
            # 2. In elections ke candidates nikalen
            cur.execute("""
                SELECT id, name, position, party, election_id, image_url, vote_count, image_url as image 
                FROM candidates 
                WHERE election_id IN %s
            """, (tuple(election_ids),))
        else:
            # Pura data (Admin ya general view ke liye)
            cur.execute("SELECT id, name, position, party, election_id, image_url, vote_count, image_url as image FROM candidates")
            
        results = cur.fetchall()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def add_candidate(candidate: CandidateCreate):
    """API for adding a new candidate (Security Removed)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # 1. Skip strictly checking Election ID if it's a string code like 'ELEC-001'
        # This allows linking Admin and User apps even without a formal Election record
        pass 

        # 2. Handle Base64 Image Upload
        image_url = ""
        
        # Admin App se kisi bhi field mein data aa sakta hai
        # Check image_base64, image, photo, AND image_url (for cases where frontend sends base64 there)
        raw_image_data = candidate.image_base64 or candidate.image or candidate.photo or candidate.image_url
        
        if raw_image_data and str(raw_image_data).startswith("data:image"):
            try:
                print(f"Received Base64 image. Data length: {len(raw_image_data)}")
                clean_base64 = raw_image_data.strip()
                
                header = ""
                if "," in clean_base64:
                    header, encoded = clean_base64.split(",", 1)
                else:
                    encoded = clean_base64
                
                data = base64.b64decode(encoded)
                
                # Extension detect karein
                ext = "jpg"
                if "png" in header.lower(): ext = "png"
                elif "webp" in header.lower(): ext = "webp"
                
                filename = f"cand_{uuid.uuid4()}.{ext}"
                filepath = os.path.join(UPLOAD_DIR, filename)
                
                with open(filepath, "wb") as f:
                    f.write(data)
                
                # Full URL banayein (User app ke liye)
                image_url = f"{BASE_URL}/uploads/{filename}"
                print(f"SUCCESS: Image saved. URL: {image_url}")
            except Exception as e:
                print(f"ERROR: Image process failed: {str(e)}")

        # 3. Insert Candidate
        cur.execute(
            """
            INSERT INTO candidates (name, position, party, election_id, image_url, vote_count)
            VALUES (%s, %s, %s, %s, %s, 0)
            RETURNING id, name, position, party, election_id, image_url, vote_count
            """,
            (candidate.name, candidate.position, candidate.party, candidate.election_id, image_url)
        )
        row = cur.fetchone()
        conn.commit()
        
        # Prepare response (ensure both image and imageUrl are set)
        response = dict(row)
        # Add alias fields for frontend mapping
        response["image"] = response["image_url"]
        return response
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.put("/candidates/{id}", response_model=CandidateResponse)
def update_candidate(id: int, candidate: CandidateCreate):
    """Admin calls this to edit candidate details and potentially update image"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # Get old candidate to see if we need to delete old image
        cur.execute("SELECT image_url FROM candidates WHERE id = %s", (id,))
        old_data = cur.fetchone()
        if not old_data:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        image_url = old_data['image_url']
        
        # Handle New Image if provided (as Base64)
        raw_image_data = candidate.image_base64 or candidate.image or candidate.photo or candidate.image_url
        if raw_image_data and str(raw_image_data).startswith("data:image"):
            # Delete old image file if it exists
            if old_data['image_url']:
                old_filename = old_data['image_url'].split("/")[-1]
                old_path = os.path.join(UPLOAD_DIR, old_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            # Save new image
            header, encoded = raw_image_data.split(",", 1)
            ext = "jpg"
            if "png" in header.lower(): ext = "png"
            elif "webp" in header.lower(): ext = "webp"
            
            filename = f"cand_{uuid.uuid4()}.{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(encoded))
            image_url = f"{BASE_URL}/uploads/{filename}"

        cur.execute(
            """
            UPDATE candidates 
            SET name = %s, position = %s, party = %s, election_id = %s, image_url = %s
            WHERE id = %s RETURNING id, name, position, party, election_id, image_url, vote_count
            """,
            (candidate.name, candidate.position, candidate.party, candidate.election_id, image_url, id)
        )
        row = cur.fetchone()
        conn.commit()
        
        response = dict(row)
        response["image"] = response["image_url"]
        return response
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.delete("/candidates/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(id: int):
    """Deletes candidate and their photo from storage"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # Get image URL first to delete file
        cur.execute("SELECT image_url FROM candidates WHERE id = %s", (id,))
        row = cur.fetchone()
        if row and row['image_url']:
            filename = row['image_url'].split("/")[-1]
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        
        cur.execute("DELETE FROM candidates WHERE id = %s RETURNING id", (id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Candidate not found")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

# --- ADMIN APIS (Specifically for Admin Panel) ---

@app.post("/admin/save-token")
def admin_save_token(req: TokenAddRequest):
    """Admin Pannel se token push karne ki API - Multi-Election Support"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        batch_id = f"S-{random.randint(1000, 9999)}" # S for Save (Manual)
        token_str = req.token.strip().upper()
        
        # 1. Insert Token
        cur.execute(
            "INSERT INTO voting_tokens (token, batch_id) VALUES (%s, %s) RETURNING id",
            (token_str, batch_id)
        )
        token_id = cur.fetchone()['id']
        
        # 2. Link to Elections
        for eid in req.election_ids:
            cur.execute(
                "INSERT INTO token_elections (token_id, election_id) VALUES (%s, %s)",
                (token_id, str(eid))
            )
        
        conn.commit()
        return {"status": "success", "batchId": batch_id, "token": token_str}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/admin/get-tokens")
def admin_get_all_tokens():
    """Admin Pannel: Grouped Tokens by Batch with Election Arrays"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # Step 1: Get all batches and their linked elections
        cur.execute("""
            SELECT vt.batch_id, te.election_id, COALESCE(e.name, te.election_id) as election_name
            FROM voting_tokens vt
            JOIN token_elections te ON vt.id = te.token_id
            LEFT JOIN elections e ON te.election_id::text = e.id::text OR te.election_id = e.name
            GROUP BY vt.batch_id, te.election_id, e.name
        """)
        batch_mappings = cur.fetchall()
        
        # Step 2: Get all tokens
        cur.execute("SELECT id, token, batch_id, is_used, used_at, created_at FROM voting_tokens ORDER BY created_at DESC")
        all_tokens = cur.fetchall()
        
        # Step 3: Organize into the requested structure
        groups = {}
        for row in batch_mappings:
            bid = row['batch_id'] or "SINGLE-TOKENS"
            if bid not in groups:
                groups[bid] = {"batchId": bid, "elections": [], "tokens": []}
            groups[bid]["elections"].append({"id": row['election_id'], "name": row['election_name']})
            
        for t in all_tokens:
            bid = t['batch_id'] or "SINGLE-TOKENS"
            if bid not in groups:
                 groups[bid] = {"batchId": bid, "elections": [], "tokens": []}
            groups[bid]["tokens"].append(t)
            
        return list(groups.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.delete("/admin/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_token(token_id: int):
    """Admin: Delete a specific token (Voting Control)"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM voting_tokens WHERE id = %s RETURNING id", (token_id,))
        deleted = cur.fetchone()
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Token not found")
        
        conn.commit()
    except HTTPException as he:
        conn.rollback()
        raise he
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/admin/results")
def admin_get_results():
    """Admin Pannel: Detailed results for ALL elections with candidate stats"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # 1. Get All Elections
        cur.execute("SELECT id, name, description, status, created_at FROM elections ORDER BY created_at DESC")
        elections = cur.fetchall()

        # 2. Get All Candidates with their votes
        cur.execute("""
            SELECT id, name, position, party, election_id, image_url, vote_count, image_url as image 
            FROM candidates 
            ORDER BY election_id, vote_count DESC
        """)
        all_candidates = cur.fetchall()

        # 3. Group them
        results = []
        for e in elections:
            e_id = str(e['id'])
            # Filter candidates for this election
            candidates = [c for c in all_candidates if str(c['election_id']) == e_id or c['election_id'] == e['name']]
            
            # Calculate total votes in this election
            total_election_votes = sum(c['vote_count'] for c in candidates)
            
            results.append({
                "electionId": e['id'],
                "electionName": e['name'],
                "status": e['status'],
                "totalVotes": total_election_votes,
                "candidates": candidates
            })
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

# --- Voting Tokens (Admin to Generate, User to Use) ---

@app.post("/tokens", response_model=VotingTokenResponse)
def push_token(req: TokenAddRequest):
    """Admin calls this to 'PUSH' a token to the database after generating it on frontend"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        token_str = req.token.strip().upper()
        # Insert without checking FK because election_id is now TEXT (ELEC-001)
        cur.execute(
            "INSERT INTO voting_tokens (token, election_id) VALUES (%s, %s) RETURNING id, token, election_id, is_used, used_at, created_at",
            (token_str, req.election_id)
        )
        new_token = cur.fetchone()
        conn.commit()
        return new_token
    except Exception as e:
        conn.rollback()
        if "unique constraint" in str(e).lower():
            raise HTTPException(status_code=400, detail="This token is already in the database.")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/tokens/generate")
def generate_tokens(req: TokenGenerateRequest):
    """Admin: Generate a Batch of 6-digit tokens for multiple elections"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # Generate a short batch ID
        batch_id = f"B-{random.randint(1000, 9999)}"
        generated_tokens = []
        
        for _ in range(req.count):
            # Generate a unique 6-digit numeric token
            attempts = 0
            while attempts < 10:
                token_str = ''.join(random.choices(string.digits, k=6))
                # Check for uniqueness
                cur.execute("SELECT id FROM voting_tokens WHERE token = %s", (token_str,))
                if not cur.fetchone():
                    break
                attempts += 1
                
            cur.execute(
                "INSERT INTO voting_tokens (token, batch_id) VALUES (%s, %s) RETURNING id, token, created_at", 
                (token_str, batch_id)
            )
            token_rec = cur.fetchone()
            token_id = token_rec['id']
            
            # Link to all selected elections
            for eid in req.election_ids:
                cur.execute(
                    "INSERT INTO token_elections (token_id, election_id) VALUES (%s, %s)", 
                    (token_id, str(eid))
                )
            
            generated_tokens.append(token_rec)
            
        conn.commit()
        return {
            "status": "success",
            "batchId": batch_id,
            "electionIds": [str(eid) for eid in req.election_ids],
            "tokens": generated_tokens
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/tokens")
def get_all_tokens(election_id: Optional[Union[int, str]] = None):
    """Admin calls this to see all saved/pushed tokens"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    
    query = """
        SELECT vt.id, vt.token, vt.election_id, vt.is_used, vt.used_at, vt.created_at, 
               COALESCE(e.name, 'No Election Name') as election_name 
        FROM voting_tokens vt
        LEFT JOIN elections e ON vt.election_id::text = e.id::text OR vt.election_id = e.name
    """
    
    try:
        if election_id:
            query += " WHERE vt.election_id = %s"
            cur.execute(query + " ORDER BY vt.created_at DESC", (str(election_id),))
        else:
            cur.execute(query + " ORDER BY vt.created_at DESC")
            
        results = cur.fetchall()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/access-token")
@app.post("/tokens/login")
def token_login(req: TokenLoginRequest):
    """User Login: Returns JWT and all authorized Elections/Candidates"""
    token_str = req.token.strip().upper()
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM voting_tokens WHERE token = %s", (token_str,))
    token_rec = cur.fetchone()
    
    if not token_rec:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid Token")
    
    if token_rec['is_used']:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Token already used")
    
    token_id = token_rec['id']
    
    # 1. Get all linked Elections
    cur.execute("""
        SELECT te.election_id as id, COALESCE(e.name, te.election_id) as name
        FROM token_elections te
        LEFT JOIN elections e ON te.election_id::text = e.id::text OR te.election_id = e.name
        WHERE te.token_id = %s
    """, (token_id,))
    elections = cur.fetchall()
    
    # 2. Get Candidates for all these elections
    election_ids = [e['id'] for e in elections]
    candidates = []
    if election_ids:
        cur.execute("""
            SELECT id, name, position, party, election_id, image_url, image_url as image 
            FROM candidates 
            WHERE election_id IN %s
        """, (tuple(election_ids),))
        candidates = cur.fetchall()
    
    cur.close()
    conn.close()

    # Generate JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_token = create_access_token(
        data={"sub": f"voter_{token_str}", "role": "voter", "token": token_str}, 
        expires_delta=access_token_expires
    )
    
    return {
        "status": "success",
        "accessToken": jwt_token,
        "tokenType": "bearer",
        "votingToken": token_rec['token'],
        "authorizedElections": elections,
        "candidates": candidates,
        "user": { "role": "voter", "token": token_rec['token'] }
    }

# --- Voting Logic ---

@app.post("/vote")
def vote(vote_req: VoteRequest):
    """Token-based and User-based Single-Use Voting API"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        # Case 1: Voting via Token (Single-Use, Multi-Election Support)
        if vote_req.token:
            token_str = vote_req.token.strip().upper()
            cur.execute("SELECT * FROM voting_tokens WHERE token = %s", (token_str,))
            token_rec = cur.fetchone()
            
            if not token_rec:
                raise HTTPException(status_code=404, detail="Token not found")
            if token_rec['is_used']:
                raise HTTPException(status_code=400, detail="This token has already been used and is now expired")
            
            # Identify which candidates the user wants to vote for
            target_ids = []
            if vote_req.candidate_ids:
                target_ids = vote_req.candidate_ids
            elif vote_req.candidate_id:
                target_ids = [vote_req.candidate_id]
            else:
                raise HTTPException(status_code=400, detail="Please provide at least one candidate ID to vote")

            # Validate each candidate and track elections to prevent double voting
            seen_elections = set()
            for c_id in target_ids:
                cur.execute("""
                    SELECT c.id, c.election_id 
                    FROM candidates c
                    JOIN token_elections te ON c.election_id = te.election_id
                    WHERE c.id = %s AND te.token_id = %s
                """, (c_id, token_rec['id']))
                cand_info = cur.fetchone()
                
                if not cand_info:
                    raise HTTPException(status_code=403, detail=f"Candidate ID {c_id} is not in your authorized elections")
                
                eid = cand_info['election_id']
                if eid in seen_elections:
                    raise HTTPException(status_code=400, detail=f"You can only vote for ONE candidate per election. Error at election: {eid}")
                seen_elections.add(eid)

            # --- PROCESS VOTES ---
            for c_id in target_ids:
                cur.execute("UPDATE candidates SET vote_count = vote_count + 1 WHERE id = %s", (c_id,))
            
            # --- EXPIRE TOKEN ---
            cur.execute("UPDATE voting_tokens SET is_used = TRUE, used_at = CURRENT_TIMESTAMP WHERE token = %s", (token_str,))
            
            conn.commit()
            return {
                "status": "success", 
                "message": f"Successfully cast {len(target_ids)} vote(s). Your token has now expired.",
                "votedElections": list(seen_elections)
            }

        # Case 2: Voting via User ID (Traditional, Multi-Election Support)
        elif vote_req.user_id:
            cur.execute("SELECT id, has_voted FROM users WHERE id = %s", (vote_req.user_id,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user['has_voted']:
                raise HTTPException(status_code=400, detail="User has already voted and is now restricted")

            # Identify candidates
            target_ids = []
            if vote_req.candidate_ids:
                target_ids = vote_req.candidate_ids
            elif vote_req.candidate_id:
                target_ids = [vote_req.candidate_id]
            else:
                raise HTTPException(status_code=400, detail="Please provide at least one candidate ID to vote")

            # Validate Candidates
            seen_elections = set()
            for c_id in target_ids:
                cur.execute("SELECT id, election_id FROM candidates WHERE id = %s", (c_id,))
                cand_info = cur.fetchone()
                if not cand_info:
                    raise HTTPException(status_code=404, detail=f"Candidate ID {c_id} not found")
                
                eid = cand_info['election_id']
                if eid in seen_elections:
                    raise HTTPException(status_code=400, detail=f"Double voting in election {eid} is not allowed")
                seen_elections.add(eid)

            # Process Votes
            for c_id in target_ids:
                cur.execute("UPDATE candidates SET vote_count = vote_count + 1 WHERE id = %s", (c_id,))
            
            cur.execute("UPDATE users SET has_voted = TRUE WHERE id = %s", (vote_req.user_id,))
            
            conn.commit()
            return {
                "status": "success", 
                "message": f"Successfully cast {len(target_ids)} vote(s) via User ID.",
                "votedElections": list(seen_elections)
            }
        
        else:
            raise HTTPException(status_code=400, detail="Either Token or User ID is required")
            
    except HTTPException as he:
        conn.rollback()
        raise he
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.delete("/candidates/all/clear")
def clear_all_candidates():
    """Testing ke liye sare candidates saaf karne ki API"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM candidates")
        conn.commit()
        return {"message": "Sare candidates delete ho gaye hain. Ab naya data add karein."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/results")
def get_results(token: Optional[str] = None):
    """Results grouped by election (Facilitates UI). Optional token filter."""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    try:
        election_ids = None
        if token:
            token_str = token.strip().upper()
            cur.execute("""
                SELECT te.election_id 
                FROM token_elections te
                JOIN voting_tokens vt ON te.token_id = vt.id
                WHERE vt.token = %s
            """, (token_str,))
            rows = cur.fetchall()
            election_ids = [r['election_id'] for r in rows]
            
            if not election_ids:
                return []

        # 1. Get Elections
        if election_ids:
            cur.execute("SELECT id, name, description FROM elections WHERE id::text IN %s OR name IN %s", (tuple(election_ids), tuple(election_ids)))
        else:
            cur.execute("SELECT id, name, description FROM elections")
        
        elections = cur.fetchall()

        # 2. Get Candidates
        if election_ids:
            cur.execute("SELECT id, name, position, party, election_id, image_url, vote_count, image_url as image FROM candidates WHERE election_id IN %s ORDER BY vote_count DESC", (tuple(election_ids),))
        else:
            cur.execute("SELECT id, name, position, party, election_id, image_url, vote_count, image_url as image FROM candidates ORDER BY vote_count DESC")
            
        all_candidates = cur.fetchall()

        # 3. Grouping Logic
        results = []
        for e in elections:
            e_id = str(e['id'])
            # Filter candidates for this specific election
            cand_list = [c for c in all_candidates if str(c['election_id']) == e_id or c['election_id'] == e['name']]
            
            results.append({
                "electionId": e['id'],
                "electionName": e['name'],
                "electionDescription": e['description'],
                "candidates": cand_list
            })
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/elections/{id}/tokens")
def get_election_tokens(id: str):
    """Specific election ke tokens dekhne ke liye"""
    conn = get_db_connection()
    if not conn: throw_db_error()
    cur = conn.cursor()
    cur.execute("SELECT * FROM voting_tokens WHERE election_id = %s ORDER BY created_at DESC", (id,))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results
