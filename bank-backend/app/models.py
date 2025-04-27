from pydantic import BaseModel, Field , EmailStr, validator
from datetime import date
from typing import Optional

class DepositRequest(BaseModel):
    account_id: int = Field(..., gt=0, description="Account ID to deposit into")
    amount: float = Field(..., gt=0, description="Deposit amount (must be positive)")

class WithdrawalRequest(BaseModel):
    account_id: int = Field(..., gt=0, description="Account ID to withdraw from")
    amount: float = Field(..., gt=0, description="Withdrawal amount (must be positive)")

class Transaction(BaseModel):
    from_account: int
    to_account: int
    amount: float
    description: Optional[str] = "Transfer"


class LoanApplication(BaseModel):
    account_id: int
    loan_type_id: int
    amount_paid: float = 0.0
    due_date: date


class UserLogin(BaseModel):
    email: str
    password: str = Field(..., min_length=4)

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

class Token(BaseModel):
    access_token: str
    token_type: str


class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    position: str
    email: str  
    password: str  

class CustomerCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(..., min_length=8)  
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
