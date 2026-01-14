from pydantic import BaseModel, EmailStr, ConfigDict
from pydantic.alias_generators import to_camel
from datetime import datetime
from typing import Optional, List, Union, Any

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )

# --- Auth Models ---
class Token(CamelModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# --- User Models ---
class UserRegister(CamelModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"

class UserLogin(CamelModel):
    email: EmailStr
    password: str

class UserResponse(CamelModel):
    id: int
    username: str
    email: EmailStr
    role: str
    has_voted: bool

# --- Election Models ---
class ElectionCreate(CamelModel):
    name: str
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    status: str = "upcoming"

class ElectionUpdate(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None

class ElectionResponse(CamelModel):
    id: int
    name: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    status: str
    created_at: Optional[datetime] = None

# --- Candidate Models ---
class CandidateCreate(CamelModel):
    name: str
    position: str
    party: str
    election_id: str  # Changed to str for ELEC-001 type IDs
    image_base64: Optional[str] = None
    image: Optional[str] = None
    photo: Optional[str] = None
    image_url: Optional[str] = None

class CandidateResponse(CamelModel):
    id: int
    name: str
    position: str
    party: str
    election_id: str  # Changed to str
    image_url: Optional[str] = None # Relative or Full URL
    image: Optional[str] = None     # Alias for imageUrl
    vote_count: int

# --- Vote Models ---
class VoteRequest(CamelModel):
    user_id: Optional[int] = None
    candidate_id: Optional[int] = None
    candidate_ids: Optional[List[int]] = None # Support multiple candidates for different elections
    token: Optional[str] = None # Support voting with token

# --- Voting Token Models ---
class TokenGenerateRequest(CamelModel):
    election_ids: List[Any]  # Use Any to bypass strict type checks from frontend
    count: int = 1

class VotingTokenResponse(CamelModel):
    id: int
    token: str
    batch_id: Optional[str] = None
    election_id: Optional[str] = None 
    is_used: bool
    used_at: Optional[datetime] = None
    created_at: datetime

class TokenBatchResponse(CamelModel):
    batch_id: str
    election_ids: List[str]
    election_names: List[str]
    tokens: List[VotingTokenResponse]
    created_at: datetime

class TokenLoginRequest(BaseModel):
    token: str

class TokenAddRequest(CamelModel):
    token: str
    election_ids: List[Any]
