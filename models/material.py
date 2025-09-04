from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from .base import BaseDocument, PyObjectId

class MaterialClassEnum(str, Enum):
    puc = "PUC"
    ug_course = "UG Course"
    pg_course = "PG Course"
    ugc_exams = "UGC Exams"
    professional_courses = "Professional Courses"
    competitive_exams = "Competitive Exams"

class MaterialTagEnum(str, Enum):
    top = "Top"
    featured = "Featured"
    new = "New"

class FeedbackItem(BaseModel):
    user_id: PyObjectId
    rating: int
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MaterialCreate(BaseModel):
    class_type: MaterialClassEnum = Field(..., alias="class")
    course: str
    subject: str
    module: str
    title: str
    description: str
    academic_year: str
    time_period: int
    tags: Optional[List[MaterialTagEnum]] = []
    price: Optional[float] = 0

class MaterialUpdate(BaseModel):
    class_type: Optional[MaterialClassEnum] = Field(None, alias="class")
    course: Optional[str] = None
    subject: Optional[str] = None
    module: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    academic_year: Optional[str] = None
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    time_period: Optional[int] = None
    tags: Optional[List[MaterialTagEnum]] = None
    price: Optional[float] = None
    is_active: Optional[bool] = None

class Material(BaseDocument):
    class_type: MaterialClassEnum = Field(..., alias="class")
    course: str
    subject: str
    module: str
    title: str
    description: str
    academic_year: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    time_period: int
    tags: List[MaterialTagEnum] = []
    download_count: int = 0
    price: float = 0
    feedback: List[FeedbackItem] = []
    is_active: bool = True