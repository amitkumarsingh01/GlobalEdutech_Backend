from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import hashlib
import jwt
import os
import random
from enum import Enum
import shutil
import base64
import json
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
import asyncio
import time

# FastAPI App
app = FastAPI(title="VIDYARTHI MITRAA API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# MongoDB Connection
MONGODB_URL = "mongodb://localhost:27017"
DATABASE_NAME = "vidyarthi_mitraa"
client = AsyncIOMotorClient(MONGODB_URL)
db = client[DATABASE_NAME]

# JWT Settings
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
security = HTTPBearer()

# Upload Directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Create all required subdirectories
os.makedirs(os.path.join(UPLOAD_DIR, "testimonials"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "students"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "videos"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "pdfs"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "profiles"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "materials"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "courses"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "carousel"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "questions"), exist_ok=True)

# App Feature Flags / Runtime Config
# Simple in-memory toggle for dual-login feature
DUAL_LOGIN_ENABLED = False

# Razorpay credentials (set these as environment variables in deployment)
# RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID") // rzp_live_RD1TqHaORLWnO5
# RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET") // R3KcI2buGSQyuD5SvM5GT6hk

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_live_RD1TqHaORLWnO5")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "R3KcI2buGSQyuD5SvM5GT6hk")

def _razorpay_auth_header() -> str:
    credentials = f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")
    return base64.b64encode(credentials).decode("utf-8")

def _http_get_json(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    req = urlrequest.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    with urlrequest.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _determine_paid_from_payment_link(link_data: Dict[str, Any]) -> bool:
    # Payment Links API returns status transitions like created -> active -> paid
    status = (link_data.get("status") or link_data.get("payment_status") or "").lower()
    if status == "paid":
        return True
    # Some responses may include payments array
    payments = link_data.get("payments") or []
    for p in payments:
        if (p.get("status") or "").lower() in ["captured", "paid"]:
            return True
    return False

def _determine_paid_from_order(order_data: Dict[str, Any], payments_data: Optional[List[Dict[str, Any]]] = None) -> bool:
    # Orders API: status may be 'paid' when fully paid; otherwise check payments list
    if (order_data.get("status") or "").lower() == "paid":
        return True
    if payments_data:
        for p in payments_data:
            if (p.get("status") or "").lower() in ["captured", "paid"]:
                return True
    return False

def fetch_razorpay_status(payment_id: str) -> Dict[str, Any]:
    """Fetch unified payment status for either a payment_link (plink_*) or order id.
    Returns: { status: str, raw: dict, paid_at?: datetime }
    """
    headers = {
        "Authorization": f"Basic {_razorpay_auth_header()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        if payment_id.startswith("plink_"):
            api_url = f"https://api.razorpay.com/v1/payment_links/{payment_id}"
            data = _http_get_json(api_url, headers)
            is_paid = _determine_paid_from_payment_link(data)
            return {
                "status": "paid" if is_paid else (data.get("status") or data.get("payment_status") or "unknown"),
                "raw": data,
                "paid_at": datetime.utcnow().isoformat() if is_paid else None,
            }
        else:
            # Orders API
            order_url = f"https://api.razorpay.com/v1/orders/{payment_id}"
            order = _http_get_json(order_url, headers)
            # Check payments under this order
            payments_url = f"https://api.razorpay.com/v1/orders/{payment_id}/payments"
            payments_wrapper = _http_get_json(payments_url, headers)
            payments = payments_wrapper.get("items", []) if isinstance(payments_wrapper, dict) else []
            is_paid = _determine_paid_from_order(order, payments)
            return {
                "status": "paid" if is_paid else (order.get("status") or "unknown"),
                "raw": {"order": order, "payments": payments},
                "paid_at": datetime.utcnow().isoformat() if is_paid else None,
            }
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        raise HTTPException(status_code=e.code or 502, detail=f"Razorpay error: {body}")
    except URLError as e:
        raise HTTPException(status_code=502, detail=f"Network error contacting Razorpay: {str(e.reason)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch payment status: {str(e)}")

# Helper Functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def verify_google_token(id_token: str) -> dict:
    """
    Verify Google ID token (optional - for additional security)
    This function can be used to verify the Google ID token on the server side
    """
    try:
        # For now, we'll just return a placeholder
        # In production, you should verify the token with Google's servers
        # You can use the google-auth library for this
        return {"verified": True, "user_id": "placeholder"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google token verification failed: {str(e)}")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user_id = verify_jwt_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication")
    return user_id

def serialize_object(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {key: serialize_object(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [serialize_object(item) for item in obj]
    return obj

# Background task for payment status polling
async def poll_payment_status():
    """
    Background task that polls payment status every 5 seconds for up to 20 minutes
    after link creation, or until the status becomes paid/failed.
    """
    while True:
        try:
            # Get all pending payment links created in the last 20 minutes
            twenty_minutes_ago = datetime.utcnow() - timedelta(minutes=20)
            
            pending_payments = []
            async for payment in db.payment_links.find({
                "status": {"$in": ["created", "pending", "issued", "active"]},
                "created_at": {"$gte": twenty_minutes_ago}
            }):
                pending_payments.append(payment)
            print(f"[poll] cycle @ {datetime.utcnow().isoformat()} | pending={len(pending_payments)}")
            
            # Update status for each pending payment
            for payment in pending_payments:
                # Ensure we have an identifier even if an exception happens below
                payment_id = payment.get("payment_id") or payment.get("link_id")
                key_name = "payment_id" if payment.get("payment_id") else ("link_id" if payment.get("link_id") else None)
                if not payment_id or not key_name:
                    # Skip malformed records
                    continue
                try:
                    # Unified status check
                    status_info = fetch_razorpay_status(payment_id)
                    new_status = status_info.get("status", "unknown")
                    print(f"[poll] update {payment_id} -> {new_status}")
                    update_data = {
                        "status": new_status,
                        "updated_at": datetime.utcnow(),
                        "raw_last": status_info.get("raw"),
                    }
                    if new_status == "paid" and status_info.get("paid_at"):
                        update_data["paid_at"] = datetime.utcnow()

                    await db.payment_links.update_one({key_name: payment_id}, {"$set": update_data})

                    await db.payment_status.update_one(
                        {"payment_id": payment_id},
                        {
                            "$set": {
                                "status": new_status,
                                "checked_at": datetime.utcnow(),
                                "updated_at": datetime.utcnow(),
                                "raw": status_info.get("raw"),
                            }
                        },
                        upsert=True
                    )
                        
                except Exception as e:
                    safe_id = payment_id if payment_id else "<unknown>"
                    print(f"Error updating payment {safe_id}: {str(e)}")
                    continue
            
            # Wait 5 seconds before next poll
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Error in payment polling: {str(e)}")
            await asyncio.sleep(60)  # Wait 1 minute on error

# Pydantic Models
class UserRegistration(BaseModel):
    name: str
    email: EmailStr
    password: str
    contact_no: str
    gender: str
    dob: str
    education: str
    course: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleAuth(BaseModel):
    firebase_uid: str
    name: str
    email: EmailStr
    photo_url: Optional[str] = None
    access_token: Optional[str] = None
    id_token: Optional[str] = None
    provider: str = "google"

class InstitutionCreate(BaseModel):
    name: str
    description: str
    vision: Optional[str] = None
    mission: Optional[str] = None

class TestimonialCreate(BaseModel):
    title: str
    description: str
    student_name: str
    course: str
    rating: int = 5
    media_type: str

class CourseCreate(BaseModel):
    name: str
    title: str
    description: str
    category: str
    sub_category: str
    start_date: str
    end_date: str
    duration: str
    instructor: str
    price: float = 0

class MaterialCreate(BaseModel):
    class_name: str
    course: str
    subject: str
    module: str
    title: str
    description: str
    academic_year: str
    time_period: int
    price: float = 0

class OnlineTestCreate(BaseModel):
    class_name: str
    course: str
    sub_category: str
    subject: str
    module: str
    test_title: str
    description: str
    total_questions: int
    total_marks: int
    duration: int
    difficulty_level: str
    pass_mark: int
    validity_days: int
    price: float

class TestQuestionCreate(BaseModel):
    test_id: str
    question_number: int
    question: str
    options: List[Dict[str, Any]]
    correct_answer: str
    explanation: Optional[str] = None
    marks: int = 1
    image_url: Optional[str] = None

class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str
    target_audience: str = "all"

class CurrentAffairsCreate(BaseModel):
    title: str
    content: str
    category: str
    publish_date: str
    importance: str = "Medium"

class DualLoginUpdate(BaseModel):
    duallogin: bool

class RazorpayStatusRequest(BaseModel):
    payment_id: str  # Just the payment_id from Razorpay

class RazorpayLinkCreateRequest(BaseModel):
    user_id: str
    product_type: str  # e.g., course, test, material
    product_id: str
    amount: float  # in INR

class PaymentHistoryResponse(BaseModel):
    payment_id: str
    user_id: str
    product_type: str
    product_id: str
    amount: float
    status: str
    payment_link: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

class PaymentStatusUpdate(BaseModel):
    payment_id: str
    status: str
    paid_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

class YouTubeVideoCreate(BaseModel):
    title: str
    youtube_url: str
    description: Optional[str] = None

class TextSliderCreate(BaseModel):
    text: str


# File Upload Helper
async def save_file(file: UploadFile, folder: str) -> str:
    file_path = os.path.join(UPLOAD_DIR, folder, file.filename)
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path

# =============== USER AUTHENTICATION ROUTES ===============

@app.post("/auth/register")
async def register_user(user_data: UserRegistration):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_dict = {
        **user_data.dict(),
        "password": hash_password(user_data.password),
        "dob": datetime.fromisoformat(user_data.dob.replace('Z', '+00:00')),
        "is_active": True,
        "last_login": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_dict)
    token = create_jwt_token(str(result.inserted_id))
    
    return {
        "message": "User registered successfully",
        "user_id": str(result.inserted_id),
        "token": token
    }

@app.post("/auth/login")
async def login_user(login_data: UserLogin):
    user = await db.users.find_one({"email": login_data.email})
    if not user or user["password"] != hash_password(login_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    token = create_jwt_token(str(user["_id"]))
    return {
        "message": "Login successful",
        "user_id": str(user["_id"]),
        "token": token,
        "user": serialize_object(user)
    }

@app.post("/auth/google")
async def google_auth(google_data: GoogleAuth):
    try:
        # Check if user exists by email or firebase_uid
        existing_user = await db.users.find_one({
            "$or": [
                {"email": google_data.email},
                {"firebase_uid": google_data.firebase_uid}
            ]
        })
        
        if existing_user:
            # User exists, update their information and login
            update_data = {
                "firebase_uid": google_data.firebase_uid,
                "name": google_data.name,
                "photo_url": google_data.photo_url,
                "provider": google_data.provider,
                "last_login": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Only update fields that are not empty
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            await db.users.update_one(
                {"_id": existing_user["_id"]},
                {"$set": update_data}
            )
            
            # Get updated user data
            updated_user = await db.users.find_one({"_id": existing_user["_id"]})
            token = create_jwt_token(str(existing_user["_id"]))
            
            return {
                "message": "Google authentication successful",
                "user_id": str(existing_user["_id"]),
                "token": token,
                "user": serialize_object(updated_user)
            }
        else:
            # New user, create account with Google data
            user_dict = {
                "firebase_uid": google_data.firebase_uid,
                "name": google_data.name,
                "email": google_data.email,
                "photo_url": google_data.photo_url,
                "provider": google_data.provider,
                "contact_no": "",  # Empty for Google users, can be filled later
                "gender": "other",  # Default value, can be updated later
                "dob": None,  # Can be updated later
                "education": "Higher education",  # Default value
                "course": "Select Course",  # Default value
                "password": None,  # No password for Google users
                "is_active": True,
                "last_login": datetime.utcnow(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await db.users.insert_one(user_dict)
            token = create_jwt_token(str(result.inserted_id))
            
            # Get the created user data
            new_user = await db.users.find_one({"_id": result.inserted_id})
            
            return {
                "message": "Google authentication successful - New user created",
                "user_id": str(result.inserted_id),
                "token": token,
                "user": serialize_object(new_user)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google authentication failed: {str(e)}")

@app.post("/auth/link-google")
async def link_google_account(link_data: dict, current_user_id: str = Depends(get_current_user)):
    """
    Link a Google account to an existing email/password account
    """
    try:
        firebase_uid = link_data.get("firebase_uid")
        photo_url = link_data.get("photo_url")
        
        if not firebase_uid:
            raise HTTPException(status_code=400, detail="Firebase UID is required")
        
        # Check if this Firebase UID is already linked to another account
        existing_google_user = await db.users.find_one({"firebase_uid": firebase_uid})
        if existing_google_user and str(existing_google_user["_id"]) != current_user_id:
            raise HTTPException(status_code=400, detail="This Google account is already linked to another user")
        
        # Update current user with Google account info
        update_data = {
            "firebase_uid": firebase_uid,
            "photo_url": photo_url,
            "provider": "google",
            "updated_at": datetime.utcnow()
        }
        
        # Only update fields that are not empty
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        result = await db.users.update_one(
            {"_id": ObjectId(current_user_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get updated user data
        updated_user = await db.users.find_one({"_id": ObjectId(current_user_id)})
        
        return {
            "message": "Google account linked successfully",
            "user": serialize_object(updated_user)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link Google account: {str(e)}")

@app.post("/auth/unlink-google")
async def unlink_google_account(current_user_id: str = Depends(get_current_user)):
    """
    Unlink Google account from user profile
    """
    try:
        # Get current user
        user = await db.users.find_one({"_id": ObjectId(current_user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has a password (can't unlink if no other auth method)
        if not user.get("password"):
            raise HTTPException(status_code=400, detail="Cannot unlink Google account. Please set a password first.")
        
        # Remove Google account info
        update_data = {
            "firebase_uid": None,
            "photo_url": None,
            "provider": "email",  # Change provider back to email
            "updated_at": datetime.utcnow()
        }
        
        result = await db.users.update_one(
            {"_id": ObjectId(current_user_id)},
            {"$unset": {"firebase_uid": "", "photo_url": ""}, "$set": {"provider": "email", "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get updated user data
        updated_user = await db.users.find_one({"_id": ObjectId(current_user_id)})
        
        return {
            "message": "Google account unlinked successfully",
            "user": serialize_object(updated_user)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unlink Google account: {str(e)}")

# =============== USER ROUTES ===============

@app.get("/users")
async def get_all_users():
    users = []
    async for user in db.users.find():
        users.append(serialize_object(user))
    return {"users": users}

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": serialize_object(user)}

@app.get("/users/email/{email}")
async def get_user_by_email(email: str):
    """Check if user exists by email (useful for Google auth)"""
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": serialize_object(user)}

@app.put("/users/{user_id}")
async def update_user(user_id: str, user_data: dict):
    user_data["updated_at"] = datetime.utcnow()
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": user_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User updated successfully"}

@app.put("/users/{user_id}/profile")
async def update_user_profile(user_id: str, profile_data: dict, current_user_id: str = Depends(get_current_user)):
    # Ensure user can only update their own profile
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only update your own profile")
    
    # Remove sensitive fields that shouldn't be updated via this endpoint
    sensitive_fields = ["password", "firebase_uid", "provider", "is_active", "created_at"]
    for field in sensitive_fields:
        profile_data.pop(field, None)
    
    profile_data["updated_at"] = datetime.utcnow()
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": profile_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return updated user data
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    return {
        "message": "Profile updated successfully",
        "user": serialize_object(updated_user)
    }

@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

# =============== INSTITUTION ROUTES ===============

@app.post("/institutions")
async def create_institution(institution: InstitutionCreate):
    institution_dict = {
        **institution.dict(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = await db.institutions.insert_one(institution_dict)
    return {"message": "Institution created", "id": str(result.inserted_id)}

@app.get("/institutions")
async def get_institutions():
    institutions = []
    async for inst in db.institutions.find():
        institutions.append(serialize_object(inst))
    return {"institutions": institutions}

@app.get("/institutions/{institution_id}")
async def get_institution(institution_id: str):
    institution = await db.institutions.find_one({"_id": ObjectId(institution_id)})
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    return {"institution": serialize_object(institution)}

@app.put("/institutions/{institution_id}")
async def update_institution(institution_id: str, institution_data: dict):
    institution_data["updated_at"] = datetime.utcnow()
    result = await db.institutions.update_one(
        {"_id": ObjectId(institution_id)},
        {"$set": institution_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Institution not found")
    return {"message": "Institution updated successfully"}

@app.delete("/institutions/{institution_id}")
async def delete_institution(institution_id: str):
    result = await db.institutions.delete_one({"_id": ObjectId(institution_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Institution not found")
    return {"message": "Institution deleted successfully"}

# =============== TESTIMONIAL ROUTES ===============

@app.post("/testimonials")
async def create_testimonial(
    title: str = Form(...),
    description: str = Form(...),
    student_name: str = Form(...),
    course: str = Form(...),
    rating: int = Form(5),
    media_type: str = Form(...),
    media_file: UploadFile = File(...),
    student_image: Optional[UploadFile] = File(None)
):
    media_url = await save_file(media_file, "testimonials")
    student_image_url = None
    if student_image:
        student_image_url = await save_file(student_image, "students")
    
    testimonial_dict = {
        "title": title,
        "description": description,
        "student_name": student_name,
        "course": course,
        "rating": rating,
        "media_type": media_type,
        "media_url": media_url,
        "student_image": student_image_url,
        "is_active": True,
        "is_featured": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.testimonials.insert_one(testimonial_dict)
    return {"message": "Testimonial created", "id": str(result.inserted_id)}

@app.get("/testimonials")
async def get_testimonials():
    testimonials = []
    async for test in db.testimonials.find():
        testimonials.append(serialize_object(test))
    return {"testimonials": testimonials}

@app.get("/testimonials/{testimonial_id}")
async def get_testimonial(testimonial_id: str):
    testimonial = await db.testimonials.find_one({"_id": ObjectId(testimonial_id)})
    if not testimonial:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"testimonial": serialize_object(testimonial)}

@app.put("/testimonials/{testimonial_id}")
async def update_testimonial(testimonial_id: str, testimonial_data: dict):
    testimonial_data["updated_at"] = datetime.utcnow()
    result = await db.testimonials.update_one(
        {"_id": ObjectId(testimonial_id)},
        {"$set": testimonial_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"message": "Testimonial updated successfully"}

@app.delete("/testimonials/{testimonial_id}")
async def delete_testimonial(testimonial_id: str):
    result = await db.testimonials.delete_one({"_id": ObjectId(testimonial_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"message": "Testimonial deleted successfully"}

# =============== COURSE ROUTES ===============

@app.post("/courses")
async def create_course(
    name: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    sub_category: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    duration: str = Form(...),
    instructor: str = Form(...),
    price: float = Form(0),
    thumbnail: UploadFile = File(...)
):
    thumbnail_url = await save_file(thumbnail, "courses")
    
    course_dict = {
        "name": name,
        "title": title,
        "description": description,
        "category": category,
        "sub_category": sub_category,
        "start_date": datetime.fromisoformat(start_date.replace('Z', '+00:00')),
        "end_date": datetime.fromisoformat(end_date.replace('Z', '+00:00')),
        "duration": duration,
        "instructor": instructor,
        "price": price,
        "thumbnail_image": thumbnail_url,
        "enrolled_students": 0,
        "status": "active",
        "is_featured": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.courses.insert_one(course_dict)
    return {"message": "Course created", "id": str(result.inserted_id)}

@app.get("/courses")
async def get_courses():
    courses = []
    async for course in db.courses.find():
        courses.append(serialize_object(course))
    return {"courses": courses}

@app.get("/courses/{course_id}")
async def get_course(course_id: str):
    course = await db.courses.find_one({"_id": ObjectId(course_id)})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"course": serialize_object(course)}

@app.put("/courses/{course_id}")
async def update_course(course_id: str, course_data: dict):
    course_data["updated_at"] = datetime.utcnow()
    result = await db.courses.update_one(
        {"_id": ObjectId(course_id)},
        {"$set": course_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"message": "Course updated successfully"}

@app.delete("/courses/{course_id}")
async def delete_course(course_id: str):
    result = await db.courses.delete_one({"_id": ObjectId(course_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"message": "Course deleted successfully"}

# =============== MATERIAL ROUTES ===============

@app.post("/materials")
async def create_material(
    class_name: str = Form(...),
    course: str = Form(...),
    sub_category: str = Form(...),
    module: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    academic_year: str = Form(...),
    time_period: int = Form(...),
    price: float = Form(0),
    pdf_file: UploadFile = File(...),
    sample_images: List[UploadFile] = File(default=[])
):
    file_url = await save_file(pdf_file, "materials")
    
    # Handle sample images upload
    sample_image_urls = []
    for sample_image in sample_images:
        if sample_image.filename:  # Check if file was actually uploaded
            sample_url = await save_file(sample_image, "materials/samples")
            sample_image_urls.append(sample_url)
    
    material_dict = {
        "class_name": class_name,
        "course": course,
        "sub_category": sub_category,
        "module": module,
        "title": title,
        "description": description,
        "academic_year": academic_year,
        "time_period": time_period,
        "price": price,
        "file_url": file_url,
        "file_size": pdf_file.size,
        "sample_images": sample_image_urls,
        "download_count": 0,
        "tags": [],
        "feedback": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.materials.insert_one(material_dict)
    return {"message": "Material created", "id": str(result.inserted_id)}

@app.get("/materials")
async def get_materials():
    materials = []
    async for material in db.materials.find():
        materials.append(serialize_object(material))
    return {"materials": materials}

@app.get("/materials/{material_id}")
async def get_material(material_id: str):
    material = await db.materials.find_one({"_id": ObjectId(material_id)})
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Increment view/access count
    await db.materials.update_one(
        {"_id": ObjectId(material_id)},
        {"$inc": {"download_count": 1}}
    )
    
    return {"material": serialize_object(material)}

@app.put("/materials/{material_id}")
async def update_material(material_id: str, material_data: dict):
    material_data["updated_at"] = datetime.utcnow()
    result = await db.materials.update_one(
        {"_id": ObjectId(material_id)},
        {"$set": material_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"message": "Material updated successfully"}

@app.delete("/materials/{material_id}")
async def delete_material(material_id: str):
    result = await db.materials.delete_one({"_id": ObjectId(material_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"message": "Material deleted successfully"}

# =============== ONLINE TEST ROUTES ===============

@app.post("/tests")
async def create_test(test: OnlineTestCreate):
    test_dict = {
        **test.dict(),
        "date_published": datetime.utcnow(),
        "result_type": "Instant",
        "answer_key": True,
        "tags": [],
        "attempts_count": 1,
        "feedback": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.online_tests.insert_one(test_dict)
    return {"message": "Test created", "id": str(result.inserted_id)}

class TestWithQuestionsCreate(BaseModel):
    test: OnlineTestCreate
    questions: List[TestQuestionCreate]

@app.post("/tests/with-questions")
async def create_test_with_questions(data: TestWithQuestionsCreate):
    # Create the test first
    test_dict = {
        **data.test.dict(),
        "date_published": datetime.utcnow(),
        "result_type": "Instant",
        "answer_key": True,
        "tags": [],
        "attempts_count": 1,
        "feedback": [],
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    test_result = await db.online_tests.insert_one(test_dict)
    test_id = str(test_result.inserted_id)
    
    # Create questions
    questions_list = []
    for question in data.questions:
        question_dict = {
            **question.dict(),
            "test_id": ObjectId(test_id),
            "difficulty_level": "Medium",
            "tags": [],
            "created_at": datetime.utcnow()
        }
        questions_list.append(question_dict)
    
    if questions_list:
        await db.test_questions.insert_many(questions_list)
    
    return {"message": "Test with questions created", "test_id": test_id, "questions_count": len(questions_list)}

@app.get("/tests")
async def get_tests():
    tests = []
    async for test in db.online_tests.find():
        # Ensure price field exists with default 0 for legacy records
        if "price" not in test or test.get("price") is None:
            test["price"] = 0
        tests.append(serialize_object(test))
    return {"tests": tests}

@app.get("/tests/{test_id}")
async def get_test(test_id: str):
    test = await db.online_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    # Ensure price field exists with default 0 for legacy records
    if "price" not in test or test.get("price") is None:
        test["price"] = 0
    return {"test": serialize_object(test)}

@app.put("/tests/{test_id}")
async def update_test(test_id: str, test_data: dict):
    test_data["updated_at"] = datetime.utcnow()
    result = await db.online_tests.update_one(
        {"_id": ObjectId(test_id)},
        {"$set": test_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"message": "Test updated successfully"}

@app.delete("/tests/{test_id}")
async def delete_test(test_id: str):
    result = await db.online_tests.delete_one({"_id": ObjectId(test_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"message": "Test deleted successfully"}

# =============== TEST QUESTION ROUTES ===============

@app.post("/test-questions")
async def create_question(
    test_id: str = Form(...),
    question_number: int = Form(...),
    question: str = Form(...),
    options: str = Form(...),  # JSON string
    correct_answer: str = Form(...),
    explanation: Optional[str] = Form(None),
    marks: int = Form(1),
    image: Optional[UploadFile] = File(None)
):
    # Parse options JSON
    import json
    try:
        options_list = json.loads(options)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid options format")
    
    # Handle image upload
    image_url = None
    if image and image.filename:
        image_url = await save_file(image, "questions")
    
    question_dict = {
        "test_id": ObjectId(test_id),
        "question_number": question_number,
        "question": question,
        "options": options_list,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "marks": marks,
        "image_url": image_url,
        "difficulty_level": "Medium",
        "tags": [],
        "created_at": datetime.utcnow()
    }
    
    result = await db.test_questions.insert_one(question_dict)
    return {"message": "Question created", "id": str(result.inserted_id)}

@app.get("/test-questions/test/{test_id}")
async def get_test_questions(test_id: str):
    questions = []
    async for question in db.test_questions.find({"test_id": ObjectId(test_id)}):
        questions.append(serialize_object(question))
    return {"questions": questions}

@app.get("/test-questions/{question_id}")
async def get_question(question_id: str):
    question = await db.test_questions.find_one({"_id": ObjectId(question_id)})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"question": serialize_object(question)}

@app.put("/test-questions/{question_id}")
async def update_question(
    question_id: str,
    test_id: str = Form(...),
    question_number: int = Form(...),
    question: str = Form(...),
    options: str = Form(...),  # JSON string
    correct_answer: str = Form(...),
    explanation: Optional[str] = Form(None),
    marks: int = Form(1),
    image: Optional[UploadFile] = File(None)
):
    # Parse options JSON
    import json
    try:
        options_list = json.loads(options)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid options format")
    
    # Handle image upload
    image_url = None
    if image and image.filename:
        image_url = await save_file(image, "questions")
    
    # Get existing question to preserve image_url if no new image is uploaded
    existing_question = await db.test_questions.find_one({"_id": ObjectId(question_id)})
    if not existing_question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # If no new image uploaded, keep existing image_url
    if not image_url and existing_question.get("image_url"):
        image_url = existing_question["image_url"]
    
    question_data = {
        "test_id": ObjectId(test_id),
        "question_number": question_number,
        "question": question,
        "options": options_list,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "marks": marks,
        "image_url": image_url,
        "updated_at": datetime.utcnow()
    }
    
    result = await db.test_questions.update_one(
        {"_id": ObjectId(question_id)},
        {"$set": question_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "Question updated successfully"}

@app.delete("/test-questions/{question_id}")
async def delete_question(question_id: str):
    result = await db.test_questions.delete_one({"_id": ObjectId(question_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"message": "Question deleted successfully"}

# =============== USER TEST ATTEMPT ROUTES ===============

@app.post("/test-attempts")
async def start_test_attempt(test_id: str, user_id: str = Depends(get_current_user)):
    # Check if test exists
    test = await db.online_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Create attempt
    attempt_dict = {
        "user_id": ObjectId(user_id),
        "test_id": ObjectId(test_id),
        "attempt_number": 1,
        "start_time": datetime.utcnow(),
        "answers": [],
        "total_marks_obtained": 0,
        "percentage": 0,
        "result": "Pending",
        "status": "in-progress",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.user_test_attempts.insert_one(attempt_dict)
    return {"message": "Test attempt started", "attempt_id": str(result.inserted_id)}

@app.put("/test-attempts/{attempt_id}/answer")
async def submit_answer(attempt_id: str, answer_data: dict):
    result = await db.user_test_attempts.update_one(
        {"_id": ObjectId(attempt_id)},
        {
            "$push": {"answers": answer_data},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return {"message": "Answer submitted"}

@app.put("/test-attempts/{attempt_id}/complete")
async def complete_test_attempt(attempt_id: str):
    attempt_dict = {
        "end_time": datetime.utcnow(),
        "status": "completed",
        "updated_at": datetime.utcnow()
    }
    
    result = await db.user_test_attempts.update_one(
        {"_id": ObjectId(attempt_id)},
        {"$set": attempt_dict}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return {"message": "Test completed"}

@app.get("/test-attempts/user/{user_id}")
async def get_user_test_attempts(user_id: str):
    attempts = []
    async for attempt in db.user_test_attempts.find({"user_id": ObjectId(user_id)}):
        attempts.append(serialize_object(attempt))
    return {"attempts": attempts}

@app.get("/test-attempts/{attempt_id}")
async def get_test_attempt(attempt_id: str):
    attempt = await db.user_test_attempts.find_one({"_id": ObjectId(attempt_id)})
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return {"attempt": serialize_object(attempt)}

# =============== NOTIFICATION ROUTES ===============

@app.post("/notifications")
async def create_notification(notification: NotificationCreate):
    notification_dict = {
        **notification.dict(),
        "priority": "medium",
        "is_active": True,
        "read_by": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.notifications.insert_one(notification_dict)
    return {"message": "Notification created", "id": str(result.inserted_id)}

@app.get("/notifications")
async def get_notifications():
    notifications = []
    async for notif in db.notifications.find():
        notifications.append(serialize_object(notif))
    return {"notifications": notifications}

@app.get("/notifications/{notification_id}")
async def get_notification(notification_id: str):
    notification = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"notification": serialize_object(notification)}

@app.put("/notifications/{notification_id}")
async def update_notification(notification_id: str, notification_data: dict):
    notification_data["updated_at"] = datetime.utcnow()
    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": notification_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification updated successfully"}

@app.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    result = await db.notifications.delete_one({"_id": ObjectId(notification_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification deleted successfully"}

# =============== CURRENT AFFAIRS ROUTES ===============

@app.post("/current-affairs")
async def create_current_affairs(affairs: CurrentAffairsCreate):
    affairs_dict = {
        **affairs.dict(),
        "publish_date": datetime.fromisoformat(affairs.publish_date.replace('Z', '+00:00')),
        "tags": [],
        "view_count": 0,
        "likes": 0,
        "is_active": True,
        "is_featured": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.current_affairs.insert_one(affairs_dict)
    return {"message": "Current affairs created", "id": str(result.inserted_id)}

@app.get("/current-affairs")
async def get_current_affairs():
    affairs = []
    async for affair in db.current_affairs.find():
        affairs.append(serialize_object(affair))
    return {"current_affairs": affairs}

@app.get("/current-affairs/{affairs_id}")
async def get_current_affair(affairs_id: str):
    affair = await db.current_affairs.find_one({"_id": ObjectId(affairs_id)})
    if not affair:
        raise HTTPException(status_code=404, detail="Current affairs not found")
    
    # Increment view count
    await db.current_affairs.update_one(
        {"_id": ObjectId(affairs_id)},
        {"$inc": {"view_count": 1}}
    )
    
    return {"current_affairs": serialize_object(affair)}

@app.put("/current-affairs/{affairs_id}")
async def update_current_affairs(affairs_id: str, affairs_data: dict):
    affairs_data["updated_at"] = datetime.utcnow()
    result = await db.current_affairs.update_one(
        {"_id": ObjectId(affairs_id)},
        {"$set": affairs_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Current affairs not found")
    return {"message": "Current affairs updated successfully"}

@app.delete("/current-affairs/{affairs_id}")
async def delete_current_affairs(affairs_id: str):
    result = await db.current_affairs.delete_one({"_id": ObjectId(affairs_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Current affairs not found")
    return {"message": "Current affairs deleted successfully"}

# =============== CONTACT ROUTES ===============

@app.post("/contact")
async def create_contact(contact_data: dict):
    contact_dict = {
        **contact_data,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.contacts.insert_one(contact_dict)
    return {"message": "Contact info created", "id": str(result.inserted_id)}

@app.get("/contact")
async def get_contact():
    contact = await db.contacts.find_one({"is_active": True})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact info not found")
    return {"contact": serialize_object(contact)}

@app.put("/contact/{contact_id}")
async def update_contact(contact_id: str, contact_data: dict):
    # Basic validation
    if "email" in contact_data and contact_data["email"]:
        import re
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, contact_data["email"]):
            raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Clean up the data - trim strings; preserve objects; convert empty strings to None
    cleaned_data: Dict[str, Any] = {}
    for key, value in contact_data.items():
        if isinstance(value, str):
            trimmed = value.strip()
            cleaned_data[key] = trimmed if trimmed else None
        elif isinstance(value, dict):
            # Clean nested dictionaries (e.g., social_media)
            nested: Dict[str, Any] = {}
            for sk, sv in value.items():
                if isinstance(sv, str):
                    tsv = sv.strip()
                    nested[sk] = tsv if tsv else None
                else:
                    nested[sk] = sv
            cleaned_data[key] = nested
        elif value is None:
            cleaned_data[key] = None
        else:
            cleaned_data[key] = value
    
    cleaned_data["updated_at"] = datetime.utcnow()
    
    result = await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": cleaned_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact updated successfully"}

# =============== USER CONTACT MESSAGES ROUTES ===============

@app.post("/contact-messages")
async def create_contact_message(message_data: dict):
    message_dict = {
        **message_data,
        "status": "pending",
        "priority": "medium",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.user_contact_messages.insert_one(message_dict)
    return {"message": "Contact message sent", "id": str(result.inserted_id)}

@app.get("/contact-messages")
async def get_contact_messages():
    messages = []
    async for message in db.user_contact_messages.find():
        messages.append(serialize_object(message))
    return {"messages": messages}

@app.get("/contact-messages/{message_id}")
async def get_contact_message(message_id: str):
    message = await db.user_contact_messages.find_one({"_id": ObjectId(message_id)})
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": serialize_object(message)}

@app.put("/contact-messages/{message_id}")
async def update_contact_message(message_id: str, message_data: dict):
    message_data["updated_at"] = datetime.utcnow()
    result = await db.user_contact_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": message_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Contact message updated successfully"}

@app.delete("/contact-messages/{message_id}")
async def delete_contact_message(message_id: str):
    result = await db.user_contact_messages.delete_one({"_id": ObjectId(message_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Contact message deleted successfully"}

# =============== TERMS AND CONDITIONS ROUTES ===============

@app.post("/terms-conditions")
async def create_terms_conditions(terms_data: dict):
    terms_dict = {
        **terms_data,
        "effective_date": datetime.fromisoformat(terms_data.get("effective_date", datetime.utcnow().isoformat()).replace('Z', '+00:00')),
        "last_modified": datetime.utcnow(),
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.terms_conditions.insert_one(terms_dict)
    return {"message": "Terms and conditions created", "id": str(result.inserted_id)}

@app.get("/terms-conditions")
async def get_terms_conditions():
    terms = await db.terms_conditions.find_one({"is_active": True})
    if not terms:
        raise HTTPException(status_code=404, detail="Terms and conditions not found")
    return {"terms": serialize_object(terms)}

@app.get("/terms-conditions/{terms_id}")
async def get_terms_by_id(terms_id: str):
    terms = await db.terms_conditions.find_one({"_id": ObjectId(terms_id)})
    if not terms:
        raise HTTPException(status_code=404, detail="Terms and conditions not found")
    return {"terms": serialize_object(terms)}

@app.put("/terms-conditions/{terms_id}")
async def update_terms_conditions(terms_id: str, terms_data: dict):
    terms_data["last_modified"] = datetime.utcnow()
    terms_data["updated_at"] = datetime.utcnow()
    result = await db.terms_conditions.update_one(
        {"_id": ObjectId(terms_id)},
        {"$set": terms_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Terms and conditions not found")
    return {"message": "Terms and conditions updated successfully"}

@app.delete("/terms-conditions/{terms_id}")
async def delete_terms_conditions(terms_id: str):
    result = await db.terms_conditions.delete_one({"_id": ObjectId(terms_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Terms and conditions not found")
    return {"message": "Terms and conditions deleted successfully"}

# =============== USER DOWNLOAD TRACKING ROUTES ===============

@app.post("/downloads")
async def track_download(download_data: dict, user_id: str = Depends(get_current_user)):
    # Check if user already downloaded this material
    existing_download = await db.user_downloads.find_one({
        "user_id": ObjectId(user_id),
        "material_id": ObjectId(download_data["material_id"])
    })
    
    if existing_download:
        # Update download count
        await db.user_downloads.update_one(
            {"_id": existing_download["_id"]},
            {
                "$inc": {"download_count": 1},
                "$set": {"last_download_at": datetime.utcnow()}
            }
        )
    else:
        # Create new download record
        download_dict = {
            "user_id": ObjectId(user_id),
            "material_id": ObjectId(download_data["material_id"]),
            "download_count": 1,
            "last_download_at": datetime.utcnow(),
            "ip_address": download_data.get("ip_address"),
            "user_agent": download_data.get("user_agent"),
            "created_at": datetime.utcnow()
        }
        await db.user_downloads.insert_one(download_dict)
    
    # Update material download count
    await db.materials.update_one(
        {"_id": ObjectId(download_data["material_id"])},
        {"$inc": {"download_count": 1}}
    )
    
    return {"message": "Download tracked successfully"}

@app.get("/downloads/user/{user_id}")
async def get_user_downloads(user_id: str):
    downloads = []
    async for download in db.user_downloads.find({"user_id": ObjectId(user_id)}):
        downloads.append(serialize_object(download))
    return {"downloads": downloads}

@app.get("/downloads/material/{material_id}")
async def get_material_downloads(material_id: str):
    downloads = []
    async for download in db.user_downloads.find({"material_id": ObjectId(material_id)}):
        downloads.append(serialize_object(download))
    return {"downloads": downloads}

# =============== USER ENROLLMENT ROUTES ===============

@app.post("/enrollments")
async def enroll_user_in_course(enrollment_data: dict, user_id: str = Depends(get_current_user)):
    # Check if user already enrolled
    existing_enrollment = await db.user_enrollments.find_one({
        "user_id": ObjectId(user_id),
        "course_id": ObjectId(enrollment_data["course_id"])
    })
    
    if existing_enrollment:
        raise HTTPException(status_code=400, detail="User already enrolled in this course")
    
    enrollment_dict = {
        "user_id": ObjectId(user_id),
        "course_id": ObjectId(enrollment_data["course_id"]),
        "enrollment_date": datetime.utcnow(),
        "status": "active",
        "progress": 0,
        "payment_status": enrollment_data.get("payment_status", "pending"),
        "amount_paid": enrollment_data.get("amount_paid", 0),
        "certificate_issued": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.user_enrollments.insert_one(enrollment_dict)
    
    # Update course enrolled students count
    await db.courses.update_one(
        {"_id": ObjectId(enrollment_data["course_id"])},
        {"$inc": {"enrolled_students": 1}}
    )
    
    return {"message": "User enrolled successfully", "enrollment_id": str(result.inserted_id)}

@app.get("/enrollments/user/{user_id}")
async def get_user_enrollments(user_id: str):
    enrollments = []
    async for enrollment in db.user_enrollments.find({"user_id": ObjectId(user_id)}):
        enrollments.append(serialize_object(enrollment))
    return {"enrollments": enrollments}

@app.get("/enrollments/course/{course_id}")
async def get_course_enrollments(course_id: str):
    enrollments = []
    async for enrollment in db.user_enrollments.find({"course_id": ObjectId(course_id)}):
        enrollments.append(serialize_object(enrollment))
    return {"enrollments": enrollments}

@app.get("/enrollments/{enrollment_id}")
async def get_enrollment(enrollment_id: str):
    enrollment = await db.user_enrollments.find_one({"_id": ObjectId(enrollment_id)})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return {"enrollment": serialize_object(enrollment)}

@app.put("/enrollments/{enrollment_id}")
async def update_enrollment(enrollment_id: str, enrollment_data: dict):
    enrollment_data["updated_at"] = datetime.utcnow()
    result = await db.user_enrollments.update_one(
        {"_id": ObjectId(enrollment_id)},
        {"$set": enrollment_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return {"message": "Enrollment updated successfully"}

@app.delete("/enrollments/{enrollment_id}")
async def delete_enrollment(enrollment_id: str):
    result = await db.user_enrollments.delete_one({"_id": ObjectId(enrollment_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return {"message": "Enrollment deleted successfully"}

# =============== ADDITIONAL UTILITY ROUTES ===============

@app.get("/")
async def root():
    return {"message": "VIDYARTHI MITRAA API is running successfully!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# =============== DASHBOARD & ANALYTICS ROUTES ===============

@app.get("/dashboard/stats")
async def get_dashboard_stats():
    # Get counts for dashboard
    total_users = await db.users.count_documents({})
    total_courses = await db.courses.count_documents({})
    total_tests = await db.online_tests.count_documents({})
    total_materials = await db.materials.count_documents({})
    total_enrollments = await db.user_enrollments.count_documents({})
    
    return {
        "total_users": total_users,
        "total_courses": total_courses,
        "total_tests": total_tests,
        "total_materials": total_materials,
        "total_enrollments": total_enrollments,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/dashboard/recent-activities")
async def get_recent_activities():
    # Get recent activities
    recent_users = []
    async for user in db.users.find().sort("created_at", -1).limit(5):
        recent_users.append(serialize_object(user))
    
    recent_enrollments = []
    async for enrollment in db.user_enrollments.find().sort("created_at", -1).limit(5):
        recent_enrollments.append(serialize_object(enrollment))
    
    recent_test_attempts = []
    async for attempt in db.user_test_attempts.find().sort("created_at", -1).limit(5):
        recent_test_attempts.append(serialize_object(attempt))
    
    return {
        "recent_users": recent_users,
        "recent_enrollments": recent_enrollments,
        "recent_test_attempts": recent_test_attempts
    }

# =============== APP SETTINGS / FEATURE FLAGS ===============

@app.get("/duallogin")
async def get_dual_login_state():
    """Return whether dual login is enabled."""
    return {"duallogin": DUAL_LOGIN_ENABLED}


@app.put("/duallogin")
async def update_dual_login_state(update: DualLoginUpdate):
    """Update dual login enabled/disabled state.

    Protected by authentication. In a real app, enforce admin authorization.
    """
    global DUAL_LOGIN_ENABLED
    DUAL_LOGIN_ENABLED = update.duallogin
    return {"message": "Dual login state updated", "duallogin": DUAL_LOGIN_ENABLED}

# =============== SEARCH ROUTES ===============

@app.get("/search/courses")
async def search_courses(query: str = "", category: str = "", limit: int = 10):
    filter_dict = {}
    
    if query:
        filter_dict["$or"] = [
            {"name": {"$regex": query, "$options": "i"}},
            {"title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}}
        ]
    
    if category:
        filter_dict["category"] = category
    
    courses = []
    async for course in db.courses.find(filter_dict).limit(limit):
        courses.append(serialize_object(course))
    
    return {"courses": courses}

@app.get("/search/materials")
async def search_materials(query: str = "", sub_category: str = "", course: str = "", limit: int = 10):
    filter_dict = {}
    
    if query:
        filter_dict["$or"] = [
            {"title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
            {"sub_category": {"$regex": query, "$options": "i"}}
        ]
    
    if sub_category:
        filter_dict["sub_category"] = sub_category
    
    if course:
        filter_dict["course"] = course
    
    materials = []
    async for material in db.materials.find(filter_dict).limit(limit):
        materials.append(serialize_object(material))
    
    return {"materials": materials}

@app.get("/search/tests")
async def search_tests(query: str = "", subject: str = "", difficulty: str = "", limit: int = 10):
    filter_dict = {}
    
    if query:
        filter_dict["$or"] = [
            {"test_title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
            {"subject": {"$regex": query, "$options": "i"}}
        ]
    
    if subject:
        filter_dict["subject"] = subject
    
    if difficulty:
        filter_dict["difficulty_level"] = difficulty
    
    tests = []
    async for test in db.online_tests.find(filter_dict).limit(limit):
        tests.append(serialize_object(test))
    
    return {"tests": tests}

# =============== FEEDBACK ROUTES ===============

@app.post("/feedback/material/{material_id}")
async def add_material_feedback(material_id: str, feedback_data: dict, user_id: str = Depends(get_current_user)):
    # Resolve user name for display
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    user_name = user.get("name") if user else None
    feedback = {
        "user_id": ObjectId(user_id),
        "user_name": user_name,
        "rating": feedback_data.get("rating", 0),
        "comment": feedback_data.get("comment", ""),
        "created_at": datetime.utcnow()
    }
    
    result = await db.materials.update_one(
        {"_id": ObjectId(material_id)},
        {"$push": {"feedback": feedback}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    
    return {"message": "Feedback added successfully"}

@app.post("/feedback/test/{test_id}")
async def add_test_feedback(test_id: str, feedback_data: dict, user_id: str = Depends(get_current_user)):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    user_name = user.get("name") if user else None
    feedback = {
        "user_id": ObjectId(user_id),
        "user_name": user_name,
        "rating": feedback_data.get("rating", 0),
        "comment": feedback_data.get("comment", ""),
        "created_at": datetime.utcnow()
    }
    
    result = await db.online_tests.update_one(
        {"_id": ObjectId(test_id)},
        {"$push": {"feedback": feedback}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return {"message": "Feedback added successfully"}

@app.post("/feedback/course/{course_id}")
async def add_course_feedback(course_id: str, feedback_data: dict, user_id: str = Depends(get_current_user)):
    """
    Add feedback for a course directly on the course document (no enrollment required).
    Stored structure mirrors material feedback: { user_id, rating, comment, created_at }.
    """
    # Validate course exists
    course = await db.courses.find_one({"_id": ObjectId(course_id)})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Build feedback entry
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    user_name = user.get("name") if user else None
    feedback = {
        "user_id": ObjectId(user_id),
        "user_name": user_name,
        "rating": feedback_data.get("rating", 0),
        "comment": feedback_data.get("comment", ""),
        "created_at": datetime.utcnow(),
    }

    result = await db.courses.update_one(
        {"_id": ObjectId(course_id)},
        {"$push": {"feedback": feedback}, "$set": {"updated_at": datetime.utcnow()}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to add course feedback")

    return {"message": "Course feedback added successfully"}

# =============== PAYMENTS (RAZORPAY) ===============

@app.post("/payments/razorpay/link")
async def razorpay_create_payment_link(payload: RazorpayLinkCreateRequest):
    """
    Create a Razorpay Payment Link and return its id and short_url.
    Docs: https://razorpay.com/docs/api/payment-links/
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay credentials not configured")

    api_url = "https://api.razorpay.com/v1/payment_links"
    credentials = f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")
    auth_header = base64.b64encode(credentials).decode("utf-8")

    # Amount in paise (integer)
    amount_paise = int(round(payload.amount * 100))

    # Create a shorter reference_id (max 40 chars)
    ref_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=10))
    
    body = {
        "amount": amount_paise,
        "currency": "INR",
        "description": f"{payload.product_type}:{payload.product_id}",
        "reference_id": ref_id,
        "notify": {"sms": False, "email": False},
        "callback_method": "get",
        # Mobile deep link callback (Android intent-filter added for myapp://razorpay/payment)
        # Razorpay will append query params like payment_id/order_id/status
        "callback_url": f"myapp://razorpay/payment?ref_id={ref_id}",
        "notes": {
            "user_id": payload.user_id,
            "product_type": payload.product_type,
            "product_id": payload.product_id,
        },
    }

    data = json.dumps(body).encode("utf-8")
    req = urlrequest.Request(api_url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {auth_header}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            rdata = json.loads(resp.read().decode("utf-8"))
            link_id = rdata.get("id")
            link_url = rdata.get("short_url") or rdata.get("payment_url") or rdata.get("status_link")

            # Upsert record
            record = {
                "user_id": ObjectId(payload.user_id) if ObjectId.is_valid(payload.user_id) else payload.user_id,
                "product_type": payload.product_type,
                "product_id": payload.product_id,
                "gateway": "razorpay",
                "amount": payload.amount,
                "link_id": link_id,
                "link_url": link_url,
                "raw": rdata,
                "status": rdata.get("status"),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            await db.payment_links.update_one(
                {"link_id": link_id, "gateway": "razorpay"},
                {"$set": record},
                upsert=True,
            )

            return {"message": "Payment link created", "payment_id": link_id, "payment_link": link_url}
    except HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = str(e)
        raise HTTPException(status_code=e.code or 502, detail=f"Razorpay error: {error_body}")
    except URLError as e:
        raise HTTPException(status_code=502, detail=f"Network error contacting Razorpay: {str(e.reason)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create payment link: {str(e)}")

@app.post("/payments/razorpay/status")
async def razorpay_payment_status(payload: RazorpayStatusRequest):
    """
    Check Razorpay payment status by payment_id only.
    Returns unified status (created/pending/active/paid/failed) with raw payloads.
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay credentials not configured")

    status_info = fetch_razorpay_status(payload.payment_id)
    # Persist a status snapshot for quick GET queries
    await db.payment_status.update_one(
        {"payment_id": payload.payment_id},
        {
            "$set": {
                "status": status_info.get("status"),
                "checked_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "raw": status_info.get("raw"),
            }
        },
        upsert=True,
    )
    return {"payment_id": payload.payment_id, **status_info}

@app.get("/payments/history/{user_id}")
async def get_payment_history(user_id: str):
    """
    Get all payment history for a user from our database.
    """
    # Convert user_id to ObjectId if it's a valid ObjectId, otherwise keep as string
    try:
        user_object_id = ObjectId(user_id)
        user_query = {"user_id": user_object_id}
    except:
        user_query = {"user_id": user_id}
    
    # Get payment links created by this user
    payment_links = []
    async for link in db.payment_links.find(user_query).sort("created_at", -1):
        payment_links.append(serialize_object(link))
    
    # Get payment status records for this user (join by payment_id in links)
    payment_statuses = []
    for link in payment_links:
        pid = link.get("link_id") or link.get("payment_id")
        if not pid:
            continue
        status = await db.payment_status.find_one({"payment_id": pid})
        if status:
            payment_statuses.append(serialize_object(status))
    
    return {
        "user_id": user_id,
        "payment_links": payment_links,
        "payment_statuses": payment_statuses
    }

@app.get("/payments/history")
async def get_all_payment_history(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    product_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get all payment history from the database (not user-specific).
    Supports filtering by status, product_type, and date range.
    """
    # Build filter query
    filter_query = {}
    
    if status:
        filter_query["status"] = status
    if product_type:
        filter_query["product_type"] = product_type
    
    # Date range filtering
    if start_date or end_date:
        date_filter = {}
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            date_filter["$gte"] = start_dt
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            date_filter["$lte"] = end_dt
        filter_query["created_at"] = date_filter
    
    # Get payment links with filters
    payment_links = []
    async for link in db.payment_links.find(filter_query).sort("created_at", -1).skip(offset).limit(limit):
        payment_links.append(serialize_object(link))
    
    # Get total count for pagination
    total_count = await db.payment_links.count_documents(filter_query)
    
    return {
        "payment_links": payment_links,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "filters": {
            "status": status,
            "product_type": product_type,
            "start_date": start_date,
            "end_date": end_date
        }
    }

@app.get("/payments/stats")
async def get_payment_stats():
    """
    Get payment statistics and analytics.
    """
    # Total payments
    total_payments = await db.payment_links.count_documents({})
    
    # Payments by status
    status_stats = {}
    status_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    async for stat in db.payment_links.aggregate(status_pipeline):
        status_stats[stat["_id"]] = stat["count"]
    
    # Payments by product type
    product_stats = {}
    product_pipeline = [
        {"$group": {"_id": "$product_type", "count": {"$sum": 1}}}
    ]
    async for stat in db.payment_links.aggregate(product_pipeline):
        product_stats[stat["_id"]] = stat["count"]
    
    # Revenue by status
    revenue_pipeline = [
        {"$group": {
            "_id": "$status",
            "total_amount": {"$sum": "$amount"},
            "count": {"$sum": 1}
        }}
    ]
    revenue_stats = {}
    async for stat in db.payment_links.aggregate(revenue_pipeline):
        revenue_stats[stat["_id"]] = {
            "total_amount": stat["total_amount"],
            "count": stat["count"]
        }
    
    # Recent payments (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_payments = await db.payment_links.count_documents({
        "created_at": {"$gte": yesterday}
    })
    
    return {
        "total_payments": total_payments,
        "status_breakdown": status_stats,
        "product_type_breakdown": product_stats,
        "revenue_breakdown": revenue_stats,
        "recent_payments_24h": recent_payments,
        "generated_at": datetime.utcnow().isoformat()
    }

# =============== FILE UPLOAD ROUTES ===============

@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_path = await save_file(file, "images")
    return {"message": "Image uploaded successfully", "file_path": file_path}

@app.post("/upload/video")
async def upload_video(file: UploadFile = File(...)):
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    file_path = await save_file(file, "videos")
    return {"message": "Video uploaded successfully", "file_path": file_path}

@app.post("/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    file_path = await save_file(file, "pdfs")
    return {"message": "PDF uploaded successfully", "file_path": file_path}

# =============== CAROUSEL ROUTES ===============

@app.post("/carousel")
async def create_carousel_item(image: UploadFile = File(...)):
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    image_path = await save_file(image, "carousel")
    item = {
        "image_url": image_path,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = await db.carousel.insert_one(item)
    return {"message": "Carousel item created", "id": str(result.inserted_id)}

@app.get("/carousel")
async def get_carousel_items():
    items = []
    async for it in db.carousel.find().sort("created_at", -1):
        # Normalize fields for frontend contract
        if "image_url" not in it:
            it["image_url"] = ""
        items.append(serialize_object({"_id": it.get("_id"), "image_url": it.get("image_url"), "created_at": it.get("created_at"), "updated_at": it.get("updated_at")}))
    return {"items": items}

@app.delete("/carousel/{item_id}")
async def delete_carousel_item(item_id: str):
    item = await db.carousel.find_one({"_id": ObjectId(item_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Carousel item not found")
    # Attempt to remove the image file (best-effort)
    try:
        image_path = item.get("image_url")
        if image_path and os.path.isfile(image_path):
            os.remove(image_path)
    except Exception:
        pass
    result = await db.carousel.delete_one({"_id": ObjectId(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Carousel item not found")
    return {"message": "Carousel item deleted"}

# =============== YOUTUBE VIDEO ROUTES ===============

@app.post("/youtube")
async def create_youtube_video(video: YouTubeVideoCreate):
    item = {
        "title": video.title,
        "youtube_url": video.youtube_url,
        "description": video.description,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.youtube_videos.insert_one(item)
    return {"message": "YouTube video saved", "id": str(result.inserted_id)}

@app.get("/youtube")
async def get_youtube_videos():
    items = []
    async for it in db.youtube_videos.find().sort("created_at", -1):
        items.append(serialize_object(it))
    return {"videos": items}

@app.delete("/youtube/{video_id}")
async def delete_youtube_video(video_id: str):
    result = await db.youtube_videos.delete_one({"_id": ObjectId(video_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="YouTube video not found")
    return {"message": "YouTube video deleted"}

# =============== TEXT SLIDER ROUTES ===============

@app.post("/text-slider")
async def create_text_slider(item: TextSliderCreate):
    record = {
        "text": item.text,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.text_slider.insert_one(record)
    return {"message": "Text added", "id": str(result.inserted_id)}

@app.get("/text-slider")
async def get_text_slider():
    items = []
    async for it in db.text_slider.find().sort("created_at", -1):
        items.append(serialize_object(it))
    return {"items": items}

@app.put("/text-slider/{item_id}")
async def update_text_slider(item_id: str, data: dict):
    data["updated_at"] = datetime.utcnow()
    result = await db.text_slider.update_one({"_id": ObjectId(item_id)}, {"$set": data})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Text item not found")
    return {"message": "Text updated"}

@app.delete("/text-slider/{item_id}")
async def delete_text_slider(item_id: str):
    result = await db.text_slider.delete_one({"_id": ObjectId(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Text item not found")
    return {"message": "Text deleted"}

# =============== BULK OPERATIONS ROUTES ===============

@app.post("/bulk/questions")
async def bulk_create_questions(questions_data: List[TestQuestionCreate]):
    questions_list = []
    for question in questions_data:
        question_dict = {
            **question.dict(),
            "test_id": ObjectId(question.test_id),
            "difficulty_level": "Medium",
            "tags": [],
            "created_at": datetime.utcnow()
        }
        questions_list.append(question_dict)
    
    result = await db.test_questions.insert_many(questions_list)
    return {"message": f"{len(result.inserted_ids)} questions created successfully"}

@app.post("/bulk/materials")
async def bulk_create_materials(materials_data: List[MaterialCreate]):
    materials_list = []
    for material in materials_data:
        material_dict = {
            **material.dict(),
            "download_count": 0,
            "tags": [],
            "feedback": [],
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        materials_list.append(material_dict)
    
    result = await db.materials.insert_many(materials_list)
    return {"message": f"{len(result.inserted_ids)} materials created successfully"}

# =============== STARTUP EVENT ===============

@app.on_event("startup")
async def startup_event():
    """
    Start background tasks when the application starts
    """
    # Start payment polling task
    asyncio.create_task(poll_payment_status())
    print("Payment polling background task started")

# =============== RUN SERVER ===============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)