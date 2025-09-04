from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date
from enum import Enum
from .base import BaseDocument

class GenderEnum(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"

class EducationEnum(str, Enum):
    higher_education = "Higher Education"
    graduation = "Graduation"
    post_graduation = "Post Graduation"
    competitive_exam = "Competitive Exam"
    others = "Others"

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    contact_no: str
    gender: GenderEnum
    dob: date
    education: EducationEnum
    course: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    contact_no: Optional[str] = None
    gender: Optional[GenderEnum] = None
    dob: Optional[date] = None
    education: Optional[EducationEnum] = None
    course: Optional[str] = None
    profile_image: Optional[str] = None

class User(BaseDocument):
    name: str
    email: EmailStr
    password: str
    contact_no: str
    gender: GenderEnum
    dob: date
    education: EducationEnum
    course: str
    profile_image: Optional[str] = None
    is_active: bool = True
    last_login: Optional[datetime] = None

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    contact_no: str
    gender: str
    dob: date
    education: str
    course: str
    profile_image: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime