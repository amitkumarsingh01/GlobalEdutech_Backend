from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from config import get_database
from models.user import UserCreate, UserLogin, User, UserResponse
from auth import get_password_hash, verify_password, create_access_token, verify_token
from bson import ObjectId

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=dict)
async def register_user(user: UserCreate, db=Depends(get_database)):
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password and create user
    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_password
    user_dict["created_at"] = datetime.utcnow()
    user_dict["updated_at"] = datetime.utcnow()
    
    result = await db.users.insert_one(user_dict)
    
    return {
        "message": "User registered successfully",
        "user_id": str(result.inserted_id)
    }

@router.post("/login", response_model=dict)
async def login_user(user_credentials: UserLogin, db=Depends(get_database)):
    # Find user by email
    user = await db.users.find_one({"email": user_credentials.email})
    if not user or not verify_password(user_credentials.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user["_id"])})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user["_id"])
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user(user_id: str = Depends(verify_token), db=Depends(get_database)):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user["id"] = str(user["_id"])
    return UserResponse(**user)
