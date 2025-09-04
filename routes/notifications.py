from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from config import get_database
from auth import verify_token
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/", response_model=dict)
async def create_notification(
    title: str,
    message: str,
    type: str = "general",
    target_audience: str = "all",
    target_course: Optional[str] = None,
    target_class: Optional[str] = None,
    priority: str = "medium",
    scheduled_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    notification_data = {
        "title": title,
        "message": message,
        "type": type,
        "target_audience": target_audience,
        "target_course": target_course,
        "target_class": target_class,
        "priority": priority,
        "scheduled_at": scheduled_at or datetime.utcnow(),
        "expires_at": expires_at,
        "is_active": True,
        "read_by": [],
        "created_by": ObjectId(current_user),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.notifications.insert_one(notification_data)
    
    return {
        "message": "Notification created successfully",
        "notification_id": str(result.inserted_id)
    }

@router.get("/", response_model=List[dict])
async def get_notifications(
    skip: int = 0,
    limit: int = 100,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Get user details for filtering
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build query for notifications
    query = {
        "is_active": True,
        "$or": [
            {"target_audience": "all"},
            {"target_audience": "specific-course", "target_course": user["course"]},
            {"target_audience": "specific-class", "target_class": user["education"]}
        ],
        "$or": [
            {"expires_at": {"$exists": False}},
            {"expires_at": None},
            {"expires_at": {"$gte": datetime.utcnow()}}
        ]
    }
    
    notifications = await db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for notification in notifications:
        notification["id"] = str(notification["_id"])
        notification["created_by"] = str(notification.get("created_by", ""))
        # Check if user has read this notification
        notification["is_read"] = any(
            str(read_info["user_id"]) == user_id 
            for read_info in notification.get("read_by", [])
        )
    
    return notifications

@router.post("/{notification_id}/read", response_model=dict)
async def mark_notification_as_read(
    notification_id: str,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Check if already read
    notification = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Check if already read by this user
    already_read = any(
        str(read_info["user_id"]) == user_id 
        for read_info in notification.get("read_by", [])
    )
    
    if not already_read:
        await db.notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {
                "$push": {
                    "read_by": {
                        "user_id": ObjectId(user_id),
                        "read_at": datetime.utcnow()
                    }
                }
            }
        )
    
    return {"message": "Notification marked as read"}

@router.delete("/{notification_id}", response_model=dict)
async def delete_notification(
    notification_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    result = await db.notifications.delete_one({"_id": ObjectId(notification_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification deleted successfully"}