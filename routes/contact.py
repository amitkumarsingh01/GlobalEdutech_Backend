from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from config import get_database
from auth import verify_token
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/contact", tags=["Contact"])

@router.get("/info", response_model=dict)
async def get_contact_info(db=Depends(get_database)):
    contact_info = await db.contact.find_one({}, sort=[("created_at", -1)])
    if not contact_info:
        return {
            "contact_number": "+91-9876543210",
            "whatsapp_number": "+91-9876543210",
            "email": "info@vidyarthimitraa.com",
            "address": {
                "street": "123 Education Street",
                "city": "Bangalore",
                "state": "Karnataka",
                "pincode": "560001",
                "country": "India"
            }
        }
    
    contact_info["id"] = str(contact_info["_id"])
    return contact_info

@router.post("/message", response_model=dict)
async def send_contact_message(
    name: str,
    email: str,
    subject: str,
    message: str,
    phone: Optional[str] = None,
    db=Depends(get_database)
):
    message_data = {
        "name": name,
        "email": email,
        "phone": phone,
        "subject": subject,
        "message": message,
        "status": "pending",
        "priority": "medium",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.user_contact_messages.insert_one(message_data)
    
    return {
        "message": "Your message has been sent successfully",
        "message_id": str(result.inserted_id)
    }

@router.get("/messages", response_model=List[dict])
async def get_contact_messages(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: str = Depends(verify_token),
    db=Depends(get_database)
):
    query = {}
    if status:
        query["status"] = status
    
    messages = await db.user_contact_messages.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for message in messages:
        message["id"] = str(message["_id"])
        if message.get("responded_by"):
            message["responded_by"] = str(message["responded_by"])
    
    return messages

@router.put("/messages/{message_id}/respond", response_model=dict)
async def respond_to_message(
    message_id: str,
    response: str,
    status: str = "resolved",
    current_user: str = Depends(verify_token),
    db=Depends(get_database)
):
    update_data = {
        "response": response,
        "status": status,
        "responded_by": ObjectId(current_user),
        "responded_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.user_contact_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return {"message": "Response sent successfully"}
