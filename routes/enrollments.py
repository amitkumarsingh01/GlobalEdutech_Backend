from fastapi import APIRouter, Depends, HTTPException
from typing import List
from config import get_database
from models.enrollment import UserEnrollmentCreate, EnrollmentStatusEnum
from auth import verify_token
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/enrollments", tags=["Course Enrollments"])

@router.post("/", response_model=dict)
async def enroll_in_course(
    enrollment: UserEnrollmentCreate,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Check if course exists
    course = await db.courses.find_one({"_id": ObjectId(enrollment.course_id)})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check if user is already enrolled
    existing_enrollment = await db.user_enrollments.find_one({
        "user_id": ObjectId(user_id),
        "course_id": ObjectId(enrollment.course_id)
    })
    
    if existing_enrollment:
        raise HTTPException(status_code=400, detail="Already enrolled in this course")
    
    # Create enrollment
    enrollment_data = enrollment.dict()
    enrollment_data["user_id"] = ObjectId(user_id)
    enrollment_data["course_id"] = ObjectId(enrollment.course_id)
    enrollment_data["enrollment_date"] = datetime.utcnow()
    enrollment_data["created_at"] = datetime.utcnow()
    enrollment_data["updated_at"] = datetime.utcnow()
    
    result = await db.user_enrollments.insert_one(enrollment_data)
    
    # Update course enrolled students count
    await db.courses.update_one(
        {"_id": ObjectId(enrollment.course_id)},
        {"$inc": {"enrolled_students": 1}}
    )
    
    return {
        "message": "Enrolled successfully",
        "enrollment_id": str(result.inserted_id)
    }

@router.get("/my-courses", response_model=List[dict])
async def get_my_enrollments(
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Get user enrollments with course details
    enrollments = await db.user_enrollments.aggregate([
        {"$match": {"user_id": ObjectId(user_id)}},
        {"$lookup": {
            "from": "courses",
            "localField": "course_id",
            "foreignField": "_id",
            "as": "course_details"
        }},
        {"$unwind": "$course_details"},
        {"$project": {
            "_id": 1,
            "status": 1,
            "progress": 1,
            "enrollment_date": 1,
            "completion_date": 1,
            "certificate_issued": 1,
            "course_details.name": 1,
            "course_details.title": 1,
            "course_details.thumbnail_image": 1,
            "course_details.instructor": 1,
            "course_details.duration": 1
        }}
    ]).to_list(None)
    
    for enrollment in enrollments:
        enrollment["id"] = str(enrollment["_id"])
        enrollment["course_id"] = str(enrollment["course_details"]["_id"])
    
    return enrollments

@router.put("/{enrollment_id}/progress", response_model=dict)
async def update_progress(
    enrollment_id: str,
    progress: float,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    if not 0 <= progress <= 100:
        raise HTTPException(status_code=400, detail="Progress must be between 0 and 100")
    
    update_data = {"progress": progress, "updated_at": datetime.utcnow()}
    
    # If progress is 100%, mark as completed
    if progress == 100:
        update_data["status"] = EnrollmentStatusEnum.completed.value
        update_data["completion_date"] = datetime.utcnow()
    
    result = await db.user_enrollments.update_one(
        {
            "_id": ObjectId(enrollment_id),
            "user_id": ObjectId(user_id)
        },
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    
    return {"message": "Progress updated successfully"}