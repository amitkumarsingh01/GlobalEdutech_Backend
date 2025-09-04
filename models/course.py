from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from .base import BaseDocument

class CourseCategoryEnum(str, Enum):
    puc = "PUC"
    ug_courses = "UG Courses"
    pg_courses = "PG Courses"
    ugc_exams = "UGC Exams"
    professional_courses = "Professional Courses"
    competitive_exams = "Competitive Exams"

class CourseStatusEnum(str, Enum):
    active = "active"
    inactive = "inactive"
    upcoming = "upcoming"
    completed = "completed"

class SyllabusItem(BaseModel):
    module: str
    topics: List[str]

class CourseCreate(BaseModel):
    name: str
    title: str
    description: str
    category: CourseCategoryEnum
    sub_category: str
    start_date: date
    end_date: date
    duration: str
    instructor: str
    price: Optional[float] = 0
    discount_price: Optional[float] = 0
    max_students: Optional[int] = 100
    syllabus: Optional[List[SyllabusItem]] = []
    prerequisites: Optional[List[str]] = []
    tags: Optional[List[str]] = []

class CourseUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_image: Optional[str] = None
    category: Optional[CourseCategoryEnum] = None
    sub_category: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration: Optional[str] = None
    instructor: Optional[str] = None
    price: Optional[float] = None
    discount_price: Optional[float] = None
    max_students: Optional[int] = None
    syllabus: Optional[List[SyllabusItem]] = None
    prerequisites: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    status: Optional[CourseStatusEnum] = None
    is_featured: Optional[bool] = None

class Course(BaseDocument):
    name: str
    title: str
    description: str
    thumbnail_image: Optional[str] = None
    category: CourseCategoryEnum
    sub_category: str
    start_date: date
    end_date: date
    duration: str
    instructor: str
    price: float = 0
    discount_price: float = 0
    max_students: int = 100
    enrolled_students: int = 0
    syllabus: List[SyllabusItem] = []
    prerequisites: List[str] = []
    tags: List[str] = []
    status: CourseStatusEnum = CourseStatusEnum.active
    is_featured: bool = False