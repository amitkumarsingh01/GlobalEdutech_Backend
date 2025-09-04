from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from config import get_database
from models.test import OnlineTestCreate, OnlineTestUpdate, TestQuestionCreate
from auth import verify_token
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/tests", tags=["Online Tests"])

@router.post("/", response_model=dict)
async def create_test(
    test: OnlineTestCreate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    test_dict = test.dict()
    test_dict["created_at"] = datetime.utcnow()
    test_dict["updated_at"] = datetime.utcnow()
    
    result = await db.online_tests.insert_one(test_dict)
    
    return {
        "message": "Test created successfully",
        "test_id": str(result.inserted_id)
    }

@router.get("/", response_model=List[dict])
async def get_all_tests(
    skip: int = 0,
    limit: int = 100,
    class_name: Optional[str] = None,
    subject: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    db=Depends(get_database)
):
    query = {"is_active": True}
    if class_name:
        query["class"] = class_name
    if subject:
        query["subject"] = subject
    if difficulty_level:
        query["difficulty_level"] = difficulty_level
    
    tests = await db.online_tests.find(query).skip(skip).limit(limit).to_list(limit)
    for test in tests:
        test["id"] = str(test["_id"])
    return tests

@router.get("/{test_id}", response_model=dict)
async def get_test_by_id(test_id: str, db=Depends(get_database)):
    test = await db.online_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test["id"] = str(test["_id"])
    return test

@router.put("/{test_id}", response_model=dict)
async def update_test(
    test_id: str,
    test_update: OnlineTestUpdate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    update_data = {k: v for k, v in test_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.online_tests.update_one(
        {"_id": ObjectId(test_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return {"message": "Test updated successfully"}

@router.post("/{test_id}/questions", response_model=dict)
async def add_question_to_test(
    test_id: str,
    question: TestQuestionCreate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    # Check if test exists
    test = await db.online_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    question_dict = question.dict()
    question_dict["test_id"] = ObjectId(test_id)
    question_dict["created_at"] = datetime.utcnow()
    
    result = await db.test_questions.insert_one(question_dict)
    
    return {
        "message": "Question added successfully",
        "question_id": str(result.inserted_id)
    }

@router.get("/{test_id}/questions", response_model=List[dict])
async def get_test_questions(test_id: str, db=Depends(get_database)):
    questions = await db.test_questions.find({"test_id": ObjectId(test_id)}).to_list(None)
    for question in questions:
        question["id"] = str(question["_id"])
        question["test_id"] = str(question["test_id"])
    return questions

@router.post("/{test_id}/start", response_model=dict)
async def start_test_attempt(
    test_id: str,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Check if test exists
    test = await db.online_tests.find_one({"_id": ObjectId(test_id)})
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Check existing attempts
    existing_attempts = await db.user_test_attempts.count_documents({
        "user_id": ObjectId(user_id),
        "test_id": ObjectId(test_id)
    })
    
    if existing_attempts >= test.get("attempts_count", 1):
        raise HTTPException(status_code=400, detail="Maximum attempts reached")
    
    # Get test questions
    questions = await db.test_questions.find({"test_id": ObjectId(test_id)}).to_list(None)
    
    # Create attempt record
    attempt_data = {
        "user_id": ObjectId(user_id),
        "test_id": ObjectId(test_id),
        "attempt_number": existing_attempts + 1,
        "start_time": datetime.utcnow(),
        "answers": [
            {
                "question_id": ObjectId(q["_id"]),
                "question_number": q["question_number"],
                "status": "pending"
            }
            for q in questions
        ],
        "status": "in-progress",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.user_test_attempts.insert_one(attempt_data)
    
    return {
        "message": "Test started successfully",
        "attempt_id": str(result.inserted_id),
        "duration": test["duration"]
    }

@router.post("/{test_id}/submit", response_model=dict)
async def submit_test_answer(
    test_id: str,
    question_id: str,
    selected_answer: str,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Find active attempt
    attempt = await db.user_test_attempts.find_one({
        "user_id": ObjectId(user_id),
        "test_id": ObjectId(test_id),
        "status": "in-progress"
    })
    
    if not attempt:
        raise HTTPException(status_code=404, detail="No active attempt found")
    
    # Get question details
    question = await db.test_questions.find_one({"_id": ObjectId(question_id)})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Check answer
    is_correct = selected_answer == question["correct_answer"]
    marks_obtained = question["marks"] if is_correct else 0
    
    # Update answer in attempt
    await db.user_test_attempts.update_one(
        {
            "_id": attempt["_id"],
            "answers.question_id": ObjectId(question_id)
        },
        {
            "$set": {
                "answers.$.selected_answer": selected_answer,
                "answers.$.is_correct": is_correct,
                "answers.$.marks_obtained": marks_obtained,
                "answers.$.status": "completed",
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Answer submitted successfully", "is_correct": is_correct}

@router.post("/{test_id}/finish", response_model=dict)
async def finish_test(
    test_id: str,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Find active attempt
    attempt = await db.user_test_attempts.find_one({
        "user_id": ObjectId(user_id),
        "test_id": ObjectId(test_id),
        "status": "in-progress"
    })
    
    if not attempt:
        raise HTTPException(status_code=404, detail="No active attempt found")
    
    # Calculate total marks
    total_marks = sum(answer.get("marks_obtained", 0) for answer in attempt["answers"])
    
    # Get test details for pass mark
    test = await db.online_tests.find_one({"_id": ObjectId(test_id)})
    pass_mark = test["pass_mark"]
    total_possible_marks = test["total_marks"]
    
    percentage = (total_marks / total_possible_marks) * 100
    result = "Pass" if total_marks >= pass_mark else "Fail"
    
    # Update attempt
    await db.user_test_attempts.update_one(
        {"_id": attempt["_id"]},
        {
            "$set": {
                "end_time": datetime.utcnow(),
                "total_marks_obtained": total_marks,
                "percentage": percentage,
                "result": result,
                "status": "completed",
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {
        "message": "Test completed successfully",
        "total_marks": total_marks,
        "percentage": percentage,
        "result": result
    }

@router.get("/{test_id}/results/{user_id}", response_model=dict)
async def get_test_results(
    test_id: str,
    user_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    attempts = await db.user_test_attempts.find({
        "user_id": ObjectId(user_id),
        "test_id": ObjectId(test_id),
        "status": "completed"
    }).to_list(None)
    
    for attempt in attempts:
        attempt["id"] = str(attempt["_id"])
        attempt["user_id"] = str(attempt["user_id"])
        attempt["test_id"] = str(attempt["test_id"])
    
    return {"attempts": attempts}

@router.delete("/{test_id}", response_model=dict)
async def delete_test(
    test_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    # Delete test questions first
    await db.test_questions.delete_many({"test_id": ObjectId(test_id)})
    
    # Delete test
    result = await db.online_tests.delete_one({"_id": ObjectId(test_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return {"message": "Test deleted successfully"}