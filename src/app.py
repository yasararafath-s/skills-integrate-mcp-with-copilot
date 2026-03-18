"""
High School Management System API

A FastAPI application with authentication, role-based authorization, and club management
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
from pathlib import Path
from enum import Enum

# ============================================================================
# Configuration
# ============================================================================

SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# ============================================================================
# Role-Based Access Control (RBAC) Permissions Matrix
# ============================================================================
# 
# STUDENT:
#   - View all activities from active clubs
#   - View club details
#   - Sign up for activities
#   - Unregister from activities
#
# CLUB_ADMIN:
#   - All STUDENT permissions
#   - Create activities for their club
#   - Update activities for their club
#   - Delete activities from their club
#   - Update club details (name, description)
#
# FEDERATION_ADMIN:
#   - All CLUB_ADMIN permissions
#   - Create new clubs
#   - Update any club (including principal and status)
#   - Ban/activate clubs
#   - Approve/manage all activities across all clubs
#
# ============================================================================

# ============================================================================
# Enums
# ============================================================================

class UserRole(str, Enum):
    STUDENT = "student"
    CLUB_ADMIN = "club_admin"
    FEDERATION_ADMIN = "federation_admin"

class ClubStatus(str, Enum):
    ACTIVE = "active"
    BANNED = "banned"

# ============================================================================
# Models
# ============================================================================

class User(BaseModel):
    email: str
    role: UserRole
    password_hash: Optional[str] = None

class Club(BaseModel):
    id: str
    name: str
    description: str
    principal: str  # email of club admin
    status: ClubStatus = ClubStatus.ACTIVE
    members: List[str] = []  # list of member emails

class Activity(BaseModel):
    name: str
    description: str
    schedule: str
    max_participants: int
    participants: List[str] = []
    club_id: str

class TokenRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class LoginRequest(BaseModel):
    email: str
    password: str

# ============================================================================
# FastAPI Setup
# ============================================================================

app = FastAPI(
    title="Mergington High School API",
    description="API for managing clubs, activities, and memberships with authentication"
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent, "static")), name="static")

# ============================================================================
# In-Memory Storage
# ============================================================================

users_db: Dict[str, User] = {}
clubs_db: Dict[str, Club] = {}
activities_db: Dict[str, Activity] = {}

def initialize_demo_data():
    """Initialize with demo users and clubs"""
    
    # Demo users
    users_db["emma@mergington.edu"] = User(
        email="emma@mergington.edu",
        role=UserRole.FEDERATION_ADMIN,
        password_hash=generate_password_hash("admin123")
    )
    users_db["principal@mergington.edu"] = User(
        email="principal@mergington.edu",
        role=UserRole.CLUB_ADMIN,
        password_hash=generate_password_hash("club123")
    )
    users_db["michael@mergington.edu"] = User(
        email="michael@mergington.edu",
        role=UserRole.STUDENT,
        password_hash=generate_password_hash("student123")
    )
    users_db["sophia@mergington.edu"] = User(
        email="sophia@mergington.edu",
        role=UserRole.STUDENT,
        password_hash=generate_password_hash("student123")
    )
    
    # Demo clubs
    chess_club = Club(
        id="chess_club_1",
        name="Chess Club",
        description="Learn strategies and compete in chess tournaments",
        principal="principal@mergington.edu",
        status=ClubStatus.ACTIVE,
        members=["michael@mergington.edu"]
    )
    clubs_db["chess_club_1"] = chess_club
    
    prog_club = Club(
        id="prog_club_1",
        name="Programming Class",
        description="Learn programming fundamentals and build software projects",
        principal="principal@mergington.edu",
        status=ClubStatus.ACTIVE,
        members=["sophia@mergington.edu"]
    )
    clubs_db["prog_club_1"] = prog_club
    
    sports_club = Club(
        id="sports_club_1",
        name="Sports Teams",
        description="Various sports teams and gym activities",
        principal="principal@mergington.edu",
        status=ClubStatus.ACTIVE,
        members=[]
    )
    clubs_db["sports_club_1"] = sports_club
    
    # Demo activities
    activities_db["chess_1"] = Activity(
        name="Chess Club",
        description="Learn strategies and compete in chess tournaments",
        schedule="Fridays, 3:30 PM - 5:00 PM",
        max_participants=12,
        participants=["michael@mergington.edu"],
        club_id="chess_club_1"
    )
    
    activities_db["prog_1"] = Activity(
        name="Programming Class",
        description="Learn programming fundamentals and build software projects",
        schedule="Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        max_participants=20,
        participants=["sophia@mergington.edu"],
        club_id="prog_club_1"
    )
    
    activities_db["gym_1"] = Activity(
        name="Gym Class",
        description="Physical education and sports activities",
        schedule="Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        max_participants=30,
        participants=[],
        club_id="sports_club_1"
    )
    
    activities_db["soccer_1"] = Activity(
        name="Soccer Team",
        description="Join the school soccer team and compete in matches",
        schedule="Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        max_participants=22,
        participants=[],
        club_id="sports_club_1"
    )
    
    activities_db["basketball_1"] = Activity(
        name="Basketball Team",
        description="Practice and play basketball with the school team",
        schedule="Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        max_participants=15,
        participants=[],
        club_id="sports_club_1"
    )

# Initialize demo data
initialize_demo_data()

# ============================================================================
# Authentication & Authorization
# ============================================================================

def create_access_token(email: str, role: str):
    """Create JWT access token"""
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(authorization: str) -> dict:
    """Verify JWT token and return payload"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        scheme, credentials = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        
        payload = jwt.decode(credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"email": email, "role": role}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

def get_current_user(authorization: str = Header(None)) -> dict:
    """Dependency to get current authenticated user"""
    return verify_token(authorization)

def require_role(*allowed_roles: UserRole):
    """Dependency factory to check user role"""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = UserRole(current_user["role"])
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

@app.post("/auth/login")
def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    user = users_db.get(request.email)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not check_password_hash(user.password_hash, request.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(user.email, user.role.value)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "role": user.role.value
        }
    }

@app.post("/auth/register")
def register(request: LoginRequest):
    """Register a new student account"""
    if request.email in users_db:
        raise HTTPException(status_code=400, detail="User already exists")
    
    password_hash = generate_password_hash(request.password)
    user = User(email=request.email, role=UserRole.STUDENT, password_hash=password_hash)
    users_db[request.email] = user
    
    access_token = create_access_token(user.email, user.role.value)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "role": user.role.value
        }
    }

@app.get("/auth/me")
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current logged-in user info"""
    user = users_db.get(current_user["email"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "email": user.email,
        "role": user.role.value
    }

@app.get("/auth/permissions")
def get_user_permissions(current_user: dict = Depends(get_current_user)):
    """Get current user's permissions based on their role"""
    user_role = UserRole(current_user["role"])
    
    permissions = {
        "role": user_role.value,
        "permissions": []
    }
    
    # Student permissions (base)
    if user_role in [UserRole.STUDENT, UserRole.CLUB_ADMIN, UserRole.FEDERATION_ADMIN]:
        permissions["permissions"].extend([
            "view_activities",
            "view_clubs",
            "view_club_details",
            "signup_for_activity",
            "unregister_from_activity"
        ])
    
    # Club Admin permissions
    if user_role in [UserRole.CLUB_ADMIN, UserRole.FEDERATION_ADMIN]:
        permissions["permissions"].extend([
            "create_activity",
            "update_activity",
            "delete_activity",
            "update_club",
            "access_admin_panel"
        ])
    
    # Federation Admin permissions
    if user_role == UserRole.FEDERATION_ADMIN:
        permissions["permissions"].extend([
            "create_club",
            "ban_club",
            "manage_all_clubs",
            "manage_all_activities",
            "access_federation_admin_console"
        ])
    
    return permissions

# ============================================================================
# Club Management Endpoints
# ============================================================================

@app.get("/clubs")
def get_clubs(current_user: dict = Depends(get_current_user)):
    """Get all clubs (only active clubs)"""
    return {
        club_id: club.dict() 
        for club_id, club in clubs_db.items() 
        if club.status == ClubStatus.ACTIVE
    }

@app.get("/clubs/{club_id}")
def get_club(club_id: str, current_user: dict = Depends(get_current_user)):
    """Get specific club details"""
    if club_id not in clubs_db:
        raise HTTPException(status_code=404, detail="Club not found")
    
    club = clubs_db[club_id]
    if club.status == ClubStatus.BANNED:
        raise HTTPException(status_code=403, detail="Club is banned")
    
    return club.dict()

@app.post("/clubs")
def create_club(
    club_data: dict,
    current_user: dict = Depends(require_role(UserRole.FEDERATION_ADMIN))
):
    """Create a new club (Federation Admin only)"""
    club_id = club_data.get("id", f"club_{len(clubs_db)}")
    
    if club_id in clubs_db:
        raise HTTPException(status_code=400, detail="Club ID already exists")
    
    club = Club(
        id=club_id,
        name=club_data.get("name", ""),
        description=club_data.get("description", ""),
        principal=club_data.get("principal", current_user["email"]),
        status=ClubStatus.ACTIVE,
        members=[]
    )
    
    clubs_db[club_id] = club
    return club.dict()

@app.put("/clubs/{club_id}")
def update_club(
    club_id: str,
    club_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update club details (Club Admin or Federation Admin)"""
    if club_id not in clubs_db:
        raise HTTPException(status_code=404, detail="Club not found")
    
    club = clubs_db[club_id]
    user_role = UserRole(current_user["role"])
    
    # Only principal or federation admin can update
    if user_role == UserRole.CLUB_ADMIN and club.principal != current_user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this club")
    elif user_role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Students cannot update clubs")
    
    # Update club fields
    if "name" in club_data:
        club.name = club_data["name"]
    if "description" in club_data:
        club.description = club_data["description"]
    if "principal" in club_data and user_role == UserRole.FEDERATION_ADMIN:
        club.principal = club_data["principal"]
    if "status" in club_data and user_role == UserRole.FEDERATION_ADMIN:
        club.status = ClubStatus(club_data["status"])
    
    clubs_db[club_id] = club
    return club.dict()

# ============================================================================
# Activity Endpoints
# ============================================================================

@app.get("/activities")
def get_activities(current_user: dict = Depends(get_current_user)):
    """Get all activities from active clubs"""
    # Filter activities from active clubs only
    active_activities = {
        activity_id: activity.dict()
        for activity_id, activity in activities_db.items()
        if clubs_db.get(activity.club_id, Club(id="", name="", description="", principal="", status=ClubStatus.ACTIVE)).status == ClubStatus.ACTIVE
    }
    
    return active_activities

@app.get("/clubs/{club_id}/activities")
def get_club_activities(
    club_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get activities for a specific club"""
    if club_id not in clubs_db:
        raise HTTPException(status_code=404, detail="Club not found")
    
    club = clubs_db[club_id]
    if club.status == ClubStatus.BANNED:
        raise HTTPException(status_code=403, detail="Club is banned")
    
    club_activities = {
        activity_id: activity.dict()
        for activity_id, activity in activities_db.items()
        if activity.club_id == club_id
    }
    
    return club_activities

@app.post("/activities/{activity_id}/signup")
def signup_for_activity(
    activity_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Sign up for an activity (Students)"""
    if activity_id not in activities_db:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    activity = activities_db[activity_id]
    club = clubs_db.get(activity.club_id)
    
    if not club or club.status == ClubStatus.BANNED:
        raise HTTPException(status_code=403, detail="Club is banned")
    
    # Check if activity is full
    if len(activity.participants) >= activity.max_participants:
        raise HTTPException(status_code=400, detail="Activity is full")
    
    # Check if already signed up
    if current_user["email"] in activity.participants:
        raise HTTPException(status_code=400, detail="Already signed up for this activity")
    
    # Sign up
    activity.participants.append(current_user["email"])
    
    # Add to club members if not already
    if current_user["email"] not in club.members:
        club.members.append(current_user["email"])
    
    return {"message": f"Signed up for {activity.name}"}

@app.delete("/activities/{activity_id}/unregister")
def unregister_from_activity(
    activity_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Unregister from an activity"""
    if activity_id not in activities_db:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    activity = activities_db[activity_id]
    
    if current_user["email"] not in activity.participants:
        raise HTTPException(status_code=400, detail="Not signed up for this activity")
    
    activity.participants.remove(current_user["email"])
    return {"message": f"Unregistered from {activity.name}"}

@app.post("/clubs/{club_id}/activities")
def create_activity(
    club_id: str,
    activity_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Create new activity for a club (Club Admin)"""
    if club_id not in clubs_db:
        raise HTTPException(status_code=404, detail="Club not found")
    
    club = clubs_db[club_id]
    user_role = UserRole(current_user["role"])
    
    # Only principal or federation admin can create activities
    if user_role == UserRole.CLUB_ADMIN and club.principal != current_user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized to manage this club")
    elif user_role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Students cannot create activities")
    
    activity_id = activity_data.get("id", f"activity_{len(activities_db)}")
    
    activity = Activity(
        name=activity_data.get("name", ""),
        description=activity_data.get("description", ""),
        schedule=activity_data.get("schedule", ""),
        max_participants=activity_data.get("max_participants", 20),
        participants=[],
        club_id=club_id
    )
    
    activities_db[activity_id] = activity
    return activity.dict()

@app.put("/activities/{activity_id}")
def update_activity(
    activity_id: str,
    activity_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update activity (Club Admin)"""
    if activity_id not in activities_db:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    activity = activities_db[activity_id]
    club = clubs_db.get(activity.club_id)
    user_role = UserRole(current_user["role"])
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Only principal or federation admin can update
    if user_role == UserRole.CLUB_ADMIN and club.principal != current_user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    elif user_role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Students cannot update activities")
    
    # Update fields
    if "name" in activity_data:
        activity.name = activity_data["name"]
    if "description" in activity_data:
        activity.description = activity_data["description"]
    if "schedule" in activity_data:
        activity.schedule = activity_data["schedule"]
    if "max_participants" in activity_data:
        activity.max_participants = activity_data["max_participants"]
    
    activities_db[activity_id] = activity
    return activity.dict()

@app.delete("/activities/{activity_id}")
def delete_activity(
    activity_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete activity (Club Admin)"""
    if activity_id not in activities_db:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    activity = activities_db[activity_id]
    club = clubs_db.get(activity.club_id)
    user_role = UserRole(current_user["role"])
    
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Only principal or federation admin can delete
    if user_role == UserRole.CLUB_ADMIN and club.principal != current_user["email"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    elif user_role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Students cannot delete activities")
    
    del activities_db[activity_id]
    return {"message": "Activity deleted"}
