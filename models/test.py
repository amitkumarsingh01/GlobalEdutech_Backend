from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime
from .base import BaseDocument, PyObjectId

class TestTypeEnum(str, Enum):
    mcq = "MCQ"
    descriptive = "Descriptive"
    mixed = "Mixed"

class DifficultyEnum(str, Enum):
    easy = "Easy"
    medium = "Medium"
    hard = "Hard"

class TestStatusEnum(str, Enum):
    featured = "Featured"
    top = "Top"
    regular = "Regular"

class ResultTypeEnum(str, Enum):
    instant = "Instant"
    delayed = "Delayed"

class QuestionOption(BaseModel):
    option_text: str
    is_correct: bool

class TestQuestionCreate(BaseModel):
    question_number: int
    question: str
    question_type: str = "MCQ"
    options: List[QuestionOption]
    correct_answer: str
    explanation: Optional[str] = None
    marks: int = 1
    difficulty_level: DifficultyEnum = DifficultyEnum.medium
    tags: Optional[List[str]] = []

class OnlineTestCreate(BaseModel):
    class_name: str = Field(..., alias="class")
    course: str
    subject: str
    module: str
    test_title: str
    description: str
    test_type: TestTypeEnum = TestTypeEnum.mcq
    total_questions: int
    total_marks: int
    duration: int  # in minutes
    difficulty_level: DifficultyEnum
    time_period: int  # in days
    status: TestStatusEnum = TestStatusEnum.regular
    pass_mark: int
    result_type: ResultTypeEnum = ResultTypeEnum.instant
    answer_key: bool = True
    tags: Optional[List[str]] = []
    attempts_count: int = 1
    price: float = 0

class OnlineTestUpdate(BaseModel):
    class_name: Optional[str] = Field(None, alias="class")
    course: Optional[str] = None
    subject: Optional[str] = None
    module: Optional[str] = None
    test_title: Optional[str] = None
    description: Optional[str] = None
    test_type: Optional[TestTypeEnum] = None
    total_questions: Optional[int] = None
    total_marks: Optional[int] = None
    duration: Optional[int] = None
    difficulty_level: Optional[DifficultyEnum] = None
    time_period: Optional[int] = None
    status: Optional[TestStatusEnum] = None
    pass_mark: Optional[int] = None
    result_type: Optional[ResultTypeEnum] = None
    answer_key: Optional[bool] = None
    tags: Optional[List[str]] = None
    attempts_count: Optional[int] = None
    price: Optional[float] = None
    is_active: Optional[bool] = None

class OnlineTest(BaseDocument):
    class_name: str = Field(..., alias="class")
    course: str
    subject: str
    module: str
    test_title: str
    description: str
    test_type: TestTypeEnum = TestTypeEnum.mcq
    total_questions: int
    total_marks: int
    duration: int
    difficulty_level: DifficultyEnum
    time_period: int
    status: TestStatusEnum = TestStatusEnum.regular
    date_published: datetime = Field(default_factory=datetime.utcnow)
    pass_mark: int
    result_type: ResultTypeEnum = ResultTypeEnum.instant
    answer_key: bool = True
    tags: List[str] = []
    attempts_count: int = 1
    price: float = 0
    feedback: List[dict] = []
    is_active: bool = True
