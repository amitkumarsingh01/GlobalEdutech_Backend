from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from typing import List, Optional
from config import get_database
from auth import verify_token
from utils.file_handler import save_file, validate_image
from bson import ObjectId
from datetime import datetime, date

router = APIRouter(prefix="/current-affairs", tags=["Current Affairs"])

@router.post("/", response_model=dict)
async def create_current_affair(
    title: str,
    content: str,
    category: str,
    summary: Optional[str] = None,
    tags: Optional[List[str]] = None,
    source: Optional[str] = None,
    source_url: Optional[str] = None,
    publish_date: date = date.today(),
    importance: str = "Medium",
    image_file: Optional[UploadFile] = File(None),
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    image_url = None
    if image_file and validate_image(image_file):
        image_url = await save_file(image_file, "images")
    
    current_affair_data = {
        "title": title,
        "content": content,
        "summary": summary,
        "category": category,
        "tags": tags or [],
        "image_url": image_url,
        "source": source,
        "source_url": source_url,
        "publish_date": publish_date,
        "importance": importance,
        "exam_relevance": [],
        "view_count": 0,
        "likes": 0,
        "is_active": True,
        "is_featured": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.current_affairs.insert_one(current_affair_data)
    
    return {
        "message": "Current affair created successfully",
        "current_affair_id": str(result.inserted_id)
    }

@router.get("/", response_model=List[dict])
async def get_current_affairs(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    importance: Optional[str] = None,
    is_featured: Optional[bool] = None,
    db=Depends(get_database)
):
    query = {"is_active": True}
    if category:
        query["category"] = category
    if importance:
        query["importance"] = importance
    if is_featured is not None:
        query["is_featured"] = is_featured
    
    current_affairs = await db.current_affairs.find(query).sort("publish_date", -1).skip(skip).limit(limit).to_list(limit)
    
    for affair in current_affairs:
        affair["id"] = str(affair["_id"])
    
    return current_affairs

@router.get("/{affair_id}", response_model=dict)
async def get_current_affair_by_id(affair_id: str, db=Depends(get_database)):
    # Increment view count
    await db.current_affairs.update_one(
        {"_id": ObjectId(affair_id)},
        {"$inc": {"view_count": 1}}
    )
    
    affair = await db.current_affairs.find_one({"_id": ObjectId(affair_id)})
    if not affair:
        raise HTTPException(status_code=404, detail="Current affair not found")
    
    affair["id"] = str(affair["_id"])
    return affair

@router.post("/{affair_id}/like", response_model=dict)
async def like_current_affair(
    affair_id: str,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    result = await db.current_affairs.update_one(
        {"_id": ObjectId(affair_id)},
        {"$inc": {"likes": 1}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Current affair not found")
    
    return {"message": "Current affair liked successfully"}

@router.delete("/{affair_id}", response_model=dict)
async def delete_current_affair(
    affair_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    result = await db.current_affairs.delete_one({"_id": ObjectId(affair_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Current affair not found")
    
    return {"message": "Current affair deleted successfully"}
