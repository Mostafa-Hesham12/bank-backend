# app/models.py
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class Transaction(BaseModel):
    from_account: int = Field(..., gt=0, description="Sender account ID")
    to_account: int = Field(..., gt=0, description="Receiver account ID")
    amount: float = Field(..., gt=0, description="Transfer amount (must be positive)")
    description: str = Field("Transfer", max_length=100)
    date: Optional[date] = None  # Will be auto-set if not provided

class LoanApplication(BaseModel):
    account_id: int = Field(..., gt=0, description="Account ID applying for loan")
    loan_type_id: int = Field(..., gt=0, description="Loan type ID")
    amount_paid: float = Field(0.0, ge=0, description="Amount already paid")
    start_date: date = Field(default_factory=date.today)
    due_date: date = Field(..., description="Loan due date")