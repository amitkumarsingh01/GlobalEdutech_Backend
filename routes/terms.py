from fastapi import APIRouter, Depends, HTTPException
from config import get_database
from auth import verify_token
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/terms", tags=["Terms and Conditions"])

@router.get("/", response_model=dict)
async def get_terms_and_conditions(db=Depends(get_database)):
    terms = await db.terms_conditions.find_one(
        {"is_active": True},
        sort=[("effective_date", -1)]
    )
    
    if not terms:
        return {
            "title": "Terms and Conditions",
            "content": "Default terms and conditions content...",
            "version": "1.0",
            "effective_date": datetime.utcnow(),
            "last_modified": datetime.utcnow()
        }
    
    terms["id"] = str(terms["_id"])
    if terms.get("created_by"):
        terms["created_by"] = str(terms["created_by"])
    
    return terms

@router.post("/", response_model=dict)
async def create_terms_and_conditions(
    title: str,
    content: str,
    version: str,
    effective_date: datetime,
    current_user: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Deactivate previous versions
    await db.terms_conditions.update_many(
        {"is_active": True},
        {"$set": {"is_active": False}}
    )
    
    terms_data = {
        "title": title,
        "content": content,
        "version": version,
        "effective_date": effective_date,
        "last_modified": datetime.utcnow(),
        "is_active": True,
        "created_by": ObjectId(current_user),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.terms_conditions.insert_one(terms_data)
    
    return {
        "message": "Terms and conditions created successfully",
        "terms_id": str(result.inserted_id)
    }
