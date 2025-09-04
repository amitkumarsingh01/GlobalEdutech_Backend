from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from typing import List, Optional
from config import get_database
from auth import verify_token
from utils.file_handler import save_file, validate_image, validate_video
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/testimonials", tags=["Testimonials"])

@router.post("/", response_model=dict)
async def create_testimonial(
    title: str,
    description: str,
    student_name: str,
    course: str,
    rating: int = 5,
    media_type: str = "image",
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    # Validate media file
    if media_type == "image" and not validate_image(file):
        raise HTTPException(status_code=400, detail="Invalid image format")
    elif media_type == "video" and not validate_video(file):
        raise HTTPException(status_code=400, detail="Invalid video format")
    
    # Save media file
    folder = "images" if media_type == "image" else "videos"
    media_url = await save_file(file, folder)
    
    testimonial_data = {
        "title": title,
        "description": description,
        "student_name": student_name,
        "course": course,
        "rating": rating,
        "media_type": media_type,
        "media_url": media_url,
        "is_active": True,
        "is_featured": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.testimonials.insert_one(testimonial_data)
    
    return {
        "message": "Testimonial created successfully",
        "testimonial_id": str(result.inserted_id)
    }

@router.get("/", response_model=List[dict])
async def get_all_testimonials(
    skip: int = 0,
    limit: int = 100,
    is_featured: Optional[bool] = None,
    db=Depends(get_database)
):
    query = {"is_active": True}
    if is_featured is not None:
        query["is_featured"] = is_featured
    
    testimonials = await db.testimonials.find(query).skip(skip).limit(limit).to_list(limit)
    for testimonial in testimonials:
        testimonial["id"] = str(testimonial["_id"])
    return testimonials

@router.put("/{testimonial_id}", response_model=dict)
async def update_testimonial(
    testimonial_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    student_name: Optional[str] = None,
    course: Optional[str] = None,
    rating: Optional[int] = None,
    is_featured: Optional[bool] = None,
    is_active: Optional[bool] = None,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if description is not None:
        update_data["description"] = description
    if student_name is not None:
        update_data["student_name"] = student_name
    if course is not None:
        update_data["course"] = course
    if rating is not None:
        update_data["rating"] = rating
    if is_featured is not None:
        update_data["is_featured"] = is_featured
    if is_active is not None:
        update_data["is_active"] = is_active
    
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.testimonials.update_one(
        {"_id": ObjectId(testimonial_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    
    return {"message": "Testimonial updated successfully"}

@router.delete("/{testimonial_id}", response_model=dict)
async def delete_testimonial(
    testimonial_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    result = await db.testimonials.delete_one({"_id": ObjectId(testimonial_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    
    return {"message": "Testimonial deleted successfully"}
