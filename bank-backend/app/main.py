from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from app.database import supabase
from app.models import Transaction, LoanApplication

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only!
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth setup
API_KEY = "your-secret-key"  # Store in .env in production!
api_key_header = APIKeyHeader(name="X-API-Key")

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": f"Internal error: {str(exc)}"}
    )

@app.get("/accounts/{account_id}/balance")
def get_balance(account_id: int):
    """Get current balance and account status"""
    account = supabase.table("account").select( "balance, card(is_blocked), customer(first_name, last_name)" ).eq("id", account_id).execute()
    if not account.data:
        raise HTTPException(404, "Account not found")
    return {
    "balance": account.data[0]["balance"],
    "card_status": "Blocked" if account.data[0]["card"]["is_blocked"] else "Active",
    "customer_name": f"{account.data[0]['customer']['first_name']} {account.data[0]['customer']['last_name']}"
    }

@app.post("/transactions/transfer",
          status_code=status.HTTP_201_CREATED,
          tags=["Transactions"])
async def transfer_funds(
    transaction: Transaction,
    api_key: str = Depends(api_key_header)
):
    """Process money transfer between accounts with full validation"""
    
    # 1. API Key Validation
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # 2. Validate Accounts Exist
    sender = supabase.table("account").select("*").eq("id", transaction.from_account).execute()
    receiver = supabase.table("account").select("*").eq("id", transaction.to_account).execute()
    
    if not sender.data or not receiver.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more accounts not found"
        )

    # 3. Check Sufficient Balance
    if float(sender.data[0]["balance"]) < transaction.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient funds"
        )

    # 4. Validate Positive Amount
    if transaction.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Amount must be positive"
        )

    # 5. Execute Transfer (Atomic Operation)
    try:
        transfer_result = supabase.rpc("transfer_funds", {
            "sender_id": transaction.from_account,
            "receiver_id": transaction.to_account,
            "transfer_amount": transaction.amount,
            "description": transaction.description
        }).execute()
        
        return {
            "status": "success",
            "transaction_id": transfer_result.data[0]["id"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer failed: {str(e)}"
        )

@app.post("/loans/apply")
def apply_loan(application: LoanApplication):
    """Process new loan application"""
    # 1. Verify account exists
    account = supabase.table("account").select("id").eq("id", application.account_id).execute()
    if not account.data:
        raise HTTPException(404, "Account not found")

    # 2. Get loan type details
    loan_type = supabase.table("loan_type").select("*").eq("id", application.loan_type_id).execute().data[0]
    
    # 3. Create loan record
    loan_data = {
        "account_id": application.account_id,
        "loan_type_id": application.loan_type_id,
        "start_date": datetime.now().date().isoformat(),
        "due_date": (datetime.now() + timedelta(days=365)).date().isoformat(),  # 1 year term
        "amount_paid": 0.0
    }
    supabase.table("loan").insert(loan_data).execute()
    
    return {
        "message": "Loan approved",
        "details": {
            "loan_type": loan_type["type"],
            "interest_rate": loan_type["base_interest_rate"]
        }
    }

@app.put("/cards/{card_id}/status")
def update_card_status(card_id: int, is_blocked: bool):
    """Toggle card blocking status"""
    supabase.table("card").update({"is_blocked": is_blocked}).eq("id", card_id).execute()
    return {"message": f"Card {'blocked' if is_blocked else 'unblocked'}"}

@app.get("/accounts/{account_id}/statement")
def generate_statement(account_id: int, start_date: str, end_date: str):
    """Generate transaction history between dates"""
    transactions = supabase.table("transaction").select("*").eq("account_id", account_id).gte("date", start_date).lte("date", end_date).execute()
    balance = supabase.table("account").select("balance").eq("id", account_id).execute().data[0]["balance"]
    
    return {
        "account_id": account_id,
        "period": f"{start_date} to {end_date}",
        "transactions": transactions.data,
        "current_balance": balance
    }

@app.get("/health")
async def health_check():
    try:
        # Test DB connection
        supabase.table("account").select("id").limit(1).execute()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    



@app.get("/test")
def test_endpoint():
    return {"message": "API is working"}

@app.post("/auth/login")
async def login(user: UserLogin):
    # Implement Supabase auth
    pass
