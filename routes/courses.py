from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from typing import List, Optional
from config import get_database
from models.course import CourseCreate, CourseUpdate, Course
from auth import verify_token
from utils.file_handler import save_file, validate_image
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.post("/", response_model=dict)
async def create_course(
    course: CourseCreate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    course_dict = course.dict()
    course_dict["created_at"] = datetime.utcnow()
    course_dict["updated_at"] = datetime.utcnow()
    
    result = await db.courses.insert_one(course_dict)
    
    return {
        "message": "Course created successfully",
        "course_id": str(result.inserted_id)
    }

@router.get("/", response_model=List[dict])
async def get_all_courses(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    is_featured: Optional[bool] = None,
    db=Depends(get_database)
):
    query = {}
    if category:
        query["category"] = category
    if is_featured is not None:
        query["is_featured"] = is_featured
    
    courses = await db.courses.find(query).skip(skip).limit(limit).to_list(limit)
    for course in courses:
        course["id"] = str(course["_id"])
    return courses

@router.get("/{course_id}", response_model=dict)
async def get_course_by_id(course_id: str, db=Depends(get_database)):
    course = await db.courses.find_one({"_id": ObjectId(course_id)})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course["id"] = str(course["_id"])
    return course

@router.put("/{course_id}", response_model=dict)
async def update_course(
    course_id: str,
    course_update: CourseUpdate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    update_data = {k: v for k, v in course_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.courses.update_one(
        {"_id": ObjectId(course_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return {"message": "Course updated successfully"}

@router.post("/{course_id}/upload-thumbnail", response_model=dict)
async def upload_course_thumbnail(
    course_id: str,
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    if not validate_image(file):
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    file_path = await save_file(file, "images")
    
    await db.courses.update_one(
        {"_id": ObjectId(course_id)},
        {"$set": {"thumbnail_image": file_path, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Thumbnail uploaded successfully", "file_path": file_path}

@router.delete("/{course_id}", response_model=dict)
async def delete_course(
    course_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    result = await db.courses.delete_one({"_id": ObjectId(course_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return {"message": "Course deleted successfully"}
