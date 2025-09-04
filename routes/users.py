from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile
from typing import List, Optional
from config import get_database
from models.user import UserUpdate, User, UserResponse
from auth import verify_token
from utils.file_handler import save_file, validate_image
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    users = await db.users.find().skip(skip).limit(limit).to_list(limit)
    for user in users:
        user["id"] = str(user["_id"])
    return users

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user["id"] = str(user["_id"])
    return UserResponse(**user)

@router.put("/{user_id}", response_model=dict)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    # Check if user exists
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    return {"message": "User updated successfully"}

@router.post("/{user_id}/upload-profile", response_model=dict)
async def upload_profile_image(
    user_id: str,
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    # Validate image
    if not validate_image(file):
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    # Save file
    file_path = await save_file(file, "profiles")
    
    # Update user profile image
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"profile_image": file_path, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Profile image uploaded successfully", "file_path": file_path}

@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}
