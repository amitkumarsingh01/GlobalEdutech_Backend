# from routes.admin import router as admin_router
# app.include_router(admin_router)

# # routes/admin.py
# from fastapi import APIRouter, Depends, HTTPException
# from config import get_database
# from auth import verify_token
# from datetime import datetime, timedelta
# from bson import ObjectId

# router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

# @router.get("/stats", response_model=dict)
# async def get_dashboard_stats(
#     current_user: str = Depends(verify_token),
#     db=Depends(get_database)
# ):
#     # Get various statistics
#     total_users = await db.users.count_documents({"is_active": True})
#     total_courses = await db.courses.count_documents({"status": "active"})
#     total_materials = await db.materials.count_documents({"is_active": True})
#     total_tests = await db.online_tests.count_documents({"is_active": True})
#     total_testimonials = await db.testimonials.count_documents({"is_active": True})
    
#     # Recent registrations (last 30 days)
#     thirty_days_ago = datetime.utcnow() - timedelta(days=30)
#     recent_users = await db.users.count_documents({
#         "created_at": {"$gte": thirty_days_ago}
#     })
    
#     # Test attempts today
#     today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
#     today_test_attempts = await db.user_test_attempts.count_documents({
#         "created_at": {"$gte": today_start}
#     })
    
#     # Popular courses (by enrollment)
#     popular_courses = await db.courses.aggregate([
#         {"$sort": {"enrolled_students": -1}},
#         {"$limit": 5},
#         {"$project": {"name": 1, "enrolled_students": 1}}
#     ]).to_list(5)
    
#     # Download statistics
#     total_downloads = await db.user_downloads.aggregate([
#         {"$group": {"_id": None, "total": {"$sum": "$download_count"}}}
#     ]).to_list(1)
    
#     downloads_count = total_downloads[0]["total"] if total_downloads else 0
    
#     return {
#         "total_users": total_users,
#         "total_courses": total_courses,
#         "total_materials": total_materials,
#         "total_tests": total_tests,
#         "total_testimonials": total_testimonials,
#         "recent_users": recent_users,
#         "today_test_attempts": today_test_attempts,
#         "total_downloads": downloads_count,
#         "popular_courses": popular_courses
#     }

# @router.get("/users/recent", response_model=list)
# async def get_recent_users(
#     limit: int = 10,
#     current_user: str = Depends(verify_token),
#     db=Depends(get_database)
# ):
#     users = await db.users.find().sort("created_at", -1).limit(limit).to_list(limit)
#     for user in users:
#         user["id"] = str(user["_id"])
#         del user["password"]  # Don't send password
#     return users

# @router.get("/analytics/course-enrollments", response_model=dict)
# async def get_course_enrollment_analytics(
#     current_user: str = Depends(verify_token),
#     db=Depends(get_database)
# ):
#     # Enrollment by category
#     category_stats = await db.courses.aggregate([
#         {"$group": {
#             "_id": "$category",
#             "total_courses": {"$sum": 1},
#             "total_enrollments": {"$sum": "$enrolled_students"}
#         }}
#     ]).to_list(None)
    
#     # Monthly enrollment trend (last 6 months)
#     six_months_ago = datetime.utcnow() - timedelta(days=180)
#     monthly_enrollments = await db.user_enrollments.aggregate([
#         {"$match": {"enrollment_date": {"$gte": six_months_ago}}},
#         {"$group": {
#             "_id": {
#                 "year": {"$year": "$enrollment_date"},
#                 "month": {"$month": "$enrollment_date"}
#             },
#             "enrollments": {"$sum": 1}
#         }},
#         {"$sort": {"_id.year": 1, "_id.month": 1}}
#     ]).to_list(None)
    
#     return {
#         "category_stats": category_stats,
#         "monthly_enrollments": monthly_enrollments
#     }

# @router.get("/analytics/test-performance", response_model=dict)
# async def get_test_performance_analytics(
#     current_user: str = Depends(verify_token),
#     db=Depends(get_database)
# ):
#     # Average scores by subject
#     subject_performance = await db.user_test_attempts.aggregate([
#         {"$match": {"status": "completed"}},
#         {"$lookup": {
#             "from": "online_tests",
#             "localField": "test_id",
#             "foreignField": "_id",
#             "as": "test_info"
#         }},
#         {"$unwind": "$test_info"},
#         {"$group": {
#             "_id": "$test_info.subject",
#             "avg_percentage": {"$avg": "$percentage"},
#             "total_attempts": {"$sum": 1},
#             "pass_rate": {
#                 "$avg": {"$cond": [{"$eq": ["$result", "Pass"]}, 1, 0]}
#             }
#         }}
#     ]).to_list(None)
    
#     # Difficulty level performance
#     difficulty_performance = await db.user_test_attempts.aggregate([
#         {"$match": {"status": "completed"}},
#         {"$lookup": {
#             "from": "online_tests",
#             "localField": "test_id",
#             "foreignField": "_id",
#             "as": "test_info"
#         }},
#         {"$unwind": "$test_info"},
#         {"$group": {
#             "_id": "$test_info.difficulty_level",
#             "avg_percentage": {"$avg": "$percentage"},
#             "total_attempts": {"$sum": 1}
#         }}
#     ]).to_list(None)
    
#     return {
#         "subject_performance": subject_performance,
#         "difficulty_performance": difficulty_performance