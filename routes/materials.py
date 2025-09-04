from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from typing import List, Optional
from config import get_database
from models.material import MaterialCreate, MaterialUpdate, Material
from auth import verify_token
from utils.file_handler import save_file, validate_pdf
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/materials", tags=["Materials"])

@router.post("/", response_model=dict)
async def create_material(
    material: MaterialCreate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    material_dict = material.dict()
    material_dict["created_at"] = datetime.utcnow()
    material_dict["updated_at"] = datetime.utcnow()
    
    result = await db.materials.insert_one(material_dict)
    
    return {
        "message": "Material created successfully",
        "material_id": str(result.inserted_id)
    }

@router.get("/", response_model=List[dict])
async def get_all_materials(
    skip: int = 0,
    limit: int = 100,
    class_type: Optional[str] = None,
    course: Optional[str] = None,
    subject: Optional[str] = None,
    db=Depends(get_database)
):
    query = {"is_active": True}
    if class_type:
        query["class"] = class_type
    if course:
        query["course"] = course
    if subject:
        query["subject"] = subject
    
    materials = await db.materials.find(query).skip(skip).limit(limit).to_list(limit)
    for material in materials:
        material["id"] = str(material["_id"])
    return materials

@router.get("/{material_id}", response_model=dict)
async def get_material_by_id(material_id: str, db=Depends(get_database)):
    material = await db.materials.find_one({"_id": ObjectId(material_id)})
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    material["id"] = str(material["_id"])
    return material

@router.put("/{material_id}", response_model=dict)
async def update_material(
    material_id: str,
    material_update: MaterialUpdate,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    update_data = {k: v for k, v in material_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.materials.update_one(
        {"_id": ObjectId(material_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    
    return {"message": "Material updated successfully"}

@router.post("/{material_id}/upload-pdf", response_model=dict)
async def upload_material_pdf(
    material_id: str,
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    if not validate_pdf(file):
        raise HTTPException(status_code=400, detail="Invalid PDF format")
    
    file_path = await save_file(file, "pdfs")
    file_size = file.size
    
    await db.materials.update_one(
        {"_id": ObjectId(material_id)},
        {"$set": {"file_url": file_path, "file_size": file_size, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "PDF uploaded successfully", "file_path": file_path}

@router.post("/{material_id}/download", response_model=dict)
async def download_material(
    material_id: str,
    user_id: str = Depends(verify_token),
    db=Depends(get_database)
):
    # Check if material exists
    material = await db.materials.find_one({"_id": ObjectId(material_id)})
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Increment download count
    await db.materials.update_one(
        {"_id": ObjectId(material_id)},
        {"$inc": {"download_count": 1}}
    )
    
    # Track user download
    download_record = {
        "user_id": ObjectId(user_id),
        "material_id": ObjectId(material_id),
        "download_count": 1,
        "last_download_at": datetime.utcnow(),
        "created_at": datetime.utcnow()
    }
    
    existing_download = await db.user_downloads.find_one({
        "user_id": ObjectId(user_id),
        "material_id": ObjectId(material_id)
    })
    
    if existing_download:
        await db.user_downloads.update_one(
            {"_id": existing_download["_id"]},
            {
                "$inc": {"download_count": 1},
                "$set": {"last_download_at": datetime.utcnow()}
            }
        )
    else:
        await db.user_downloads.insert_one(download_record)
    
    return {
        "message": "Download recorded successfully",
        "file_url": material.get("file_url")
    }

@router.delete("/{material_id}", response_model=dict)
async def delete_material(
    material_id: str,
    db=Depends(get_database),
    current_user: str = Depends(verify_token)
):
    result = await db.materials.delete_one({"_id": ObjectId(material_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Material not found")
    
    return {"message": "Material deleted successfully"}