from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from enum import Enum
from .base import BaseDocument, PyObjectId

class EnrollmentStatusEnum(str, Enum):
    active = "active"
    completed = "completed"
    dropped = "dropped"
    suspended = "suspended"

class PaymentStatusEnum(str, Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"

class UserEnrollmentCreate(BaseModel):
    course_id: str
    payment_status: PaymentStatusEnum = PaymentStatusEnum.pending
    amount_paid: float = 0

class UserEnrollment(BaseDocument):
    user_id: PyObjectId
    course_id: PyObjectId
    enrollment_date: datetime = Field(default_factory=datetime.utcnow)
    status: EnrollmentStatusEnum = EnrollmentStatusEnum.active
    progress: float = 0  # 0-100
    completion_date: Optional[datetime] = None
    payment_status: PaymentStatusEnum = PaymentStatusEnum.pending
    amount_paid: float = 0
    payment_date: Optional[datetime] = None
    certificate_issued: bool = False
    certificate_url: Optional[str] = None
    feedback: Optional[dict] = None