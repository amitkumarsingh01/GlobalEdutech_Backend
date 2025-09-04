import aiofiles
import os
from fastapi import UploadFile, HTTPException
from typing import Optional
import uuid
from PIL import Image
from config import UPLOAD_DIR, MAX_FILE_SIZE

async def save_file(file: UploadFile, folder: str) -> str:
    """Save uploaded file and return the file path"""
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    # Generate unique filename
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = f"{UPLOAD_DIR}/{folder}/{unique_filename}"
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    return file_path

async def delete_file(file_path: str) -> bool:
    """Delete file from filesystem"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False

def validate_image(file: UploadFile) -> bool:
    """Validate if file is an image"""
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    return file.content_type in allowed_types

def validate_video(file: UploadFile) -> bool:
    """Validate if file is a video"""
    allowed_types = ["video/mp4", "video/avi", "video/mov", "video/wmv"]
    return file.content_type in allowed_types

def validate_pdf(file: UploadFile) -> bool:
    """Validate if file is a PDF"""
    return file.content_type == "application/pdf"
