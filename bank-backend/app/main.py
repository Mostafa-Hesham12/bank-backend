from fastapi import FastAPI, HTTPException, Depends, status, Request , Body
from fastapi.security import APIKeyHeader , OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from app.database import supabase
from app.models import Transaction, LoanApplication , UserLogin , Token , DepositRequest, WithdrawalRequest , CustomerCreate , EmployeeCreate
from jose import jwt, JWTError
import os

required_vars = ["SUPABASE_URL", "SUPABASE_KEY", "JWT_SECRET"]
for var in required_vars:
    if not os.environ.get(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

app = FastAPI(
    title="Banking API",
    description="API for banking operations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

SECRET_KEY = os.environ.get("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", 60))


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)




API_KEY = "your-secret-key"
api_key_header = APIKeyHeader(name="X-API-Key")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": f"Internal error: {str(exc)}"}
    )

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_data = {
            "email": payload["sub"],
            "role": payload["role"],
            "user_id": payload["user_id"]
        }
        if "linked_customer_id" in payload:
            user_data["linked_customer_id"] = payload["linked_customer_id"]
        if "linked_employee_id" in payload:
            user_data["linked_employee_id"] = payload["linked_employee_id"]
        
        return user_data
    except Exception as e:
        raise HTTPException(401, detail=f"Invalid token: {str(e)}")
    
@app.get("/admin/accounts/{account_id}/statement")
async def get_account_statement_admin(
    account_id: int,
    
):
    """Get full account statement for any account (admin/employee only)"""
    try:
        
        
        account = supabase.table("account") \
            .select("id, customer_id, balance") \
            .eq("id", account_id) \
            .execute()
        
        if not account.data:
            raise HTTPException(404, "Account not found")
        
 
        transactions = supabase.table("transaction") \
            .select("*") \
            .or_(f"from_account.eq.{account_id},to_account.eq.{account_id}") \
            .order("created_at", desc=True) \
            .execute()

    
        customer = supabase.table("customer") \
            .select("first_name, last_name") \
            .eq("id", account.data[0]["customer_id"]) \
            .execute()

      
        return {
            "account_id": account_id,
            "customer_id": account.data[0]["customer_id"],
            "customer_name": f"{customer.data[0]['first_name']} {customer.data[0]['last_name']}",
            "current_balance": account.data[0]["balance"],
            "transaction_count": len(transactions.data),
            "transactions": transactions.data 
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/accounts/balance")
def get_alance(current_user: dict = Depends(get_current_user)):
    """Get current balance and account status"""

    account_id = current_user.get("linked_customer_id")
    
    if not account_id:
        raise HTTPException(403, "No linked account found")
    
    account = supabase.table("account").select(
        "balance, card(is_blocked), customer(first_name, last_name)"
    ).eq("id", account_id).execute()
    
    if not account.data:
        raise HTTPException(404, "Account not found")
    
    return {
        "balance": account.data[0]["balance"],
        "card_status": "Blocked" if account.data[0]["card"]["is_blocked"] else "Active",
        "customer_name": f"{account.data[0]['customer']['first_name']} {account.data[0]['customer']['last_name']}"
    }

@app.post("/transactions/withdraw",
          status_code=status.HTTP_201_CREATED,
          tags=["Transactions"])
async def withdraw_funds(
    withdrawal: WithdrawalRequest,  
    current_user: dict = Depends(get_current_user),
):
    """Withdraw funds from account"""
    
    try:
        
        account_id = current_user.get("linked_customer_id")
        if not account_id:
            raise HTTPException(403, "No linked account found")

        
        account = supabase.table("account").select("customer_id, balance").eq("id", account_id).execute()
        if not account.data:
            raise HTTPException(404, "Account not found")
        
        
        if withdrawal.amount <= 0:
            raise HTTPException(400, "Amount must be positive")
        
        
        current_balance = float(account.data[0]["balance"])
        if current_balance < withdrawal.amount:
            raise HTTPException(400, "Insufficient funds")
        
        
        new_balance = current_balance - withdrawal.amount
        supabase.table("account").update({"balance": new_balance}).eq("id", account_id).execute()
        
        
        transaction_data = {
            "from_account": account_id,
            "to_account": 0,  
            "amount": float(withdrawal.amount),
            "description": "Withdrawal by customer",
            "executed_by": current_user["user_id"],
            "created_at": datetime.now().isoformat()
        }
        
        transaction_record = supabase.table("transaction").insert(transaction_data).execute()
        
        return {
            "status": "success",
            "new_balance": new_balance,
            "transaction_id": transaction_record.data[0]["id"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))
            
                
                            
        

@app.post("/transactions/deposit",
          status_code=status.HTTP_201_CREATED,
          tags=["Transactions"])
async def deposit_funds(
    deposit: DepositRequest,  
    current_user: dict = Depends(get_current_user),
):
    """Deposit funds to account"""
    
    account_id = current_user.get("linked_customer_id")
    if not account_id:
        raise HTTPException(403, "No linked account found")

    account = supabase.table("account").select("customer_id, balance").eq("id", account_id).execute()
    if not account.data:
        raise HTTPException(404, "Account not found")
    
    if deposit.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    
    new_balance = float(account.data[0]["balance"]) + deposit.amount
    supabase.table("account").update({"balance": new_balance}).eq("id", account_id).execute()
    
    transaction_data = {
        "from_account": 0,  
        "to_account": account_id,
        "amount": float(deposit.amount),
        "description": "Deposit by bank",
        "executed_by": 0, 
        "created_at": datetime.now().isoformat()
    }
    
    transaction_record=supabase.table("transaction").insert(transaction_data).execute()
    
    return {
        "status": "success",
        "new_balance": new_balance,
        "transaction_id": transaction_record.data[0]["id"] if transaction_record.data else None
    }

@app.post("/transactions/transfer")
async def transfer_funds(
    transaction: Transaction,
    current_user: dict = Depends(get_current_user)
):
    try:
        from_account = current_user.get("linked_customer_id")
        
        if not from_account:
            raise HTTPException(403, "No linked account found")

        sender_account = supabase.table("account") \
            .select("id, balance") \
            .eq("id", from_account) \
            .execute()

        if not sender_account.data:
            raise HTTPException(404, "Sender account not found")

        sender_balance = float(sender_account.data[0]["balance"])

        receiver_account = supabase.table("account") \
            .select("id, balance") \
            .eq("id", transaction.to_account) \
            .execute()

        if not receiver_account.data:
            raise HTTPException(404, "Receiver account not found")

        if sender_balance < transaction.amount:
            raise HTTPException(400, "Insufficient funds")

        new_sender_balance = sender_balance - transaction.amount  
        new_receiver_balance = float(receiver_account.data[0].get("balance", 0)) + transaction.amount


        supabase.table("account") \
            .update({"balance": new_sender_balance}) \
            .eq("id", from_account) \
            .execute()


        supabase.table("account") \
            .update({"balance": new_receiver_balance}) \
            .eq("id", transaction.to_account) \
            .execute()

        transaction_data = {
            "from_account": from_account,
            "to_account": transaction.to_account,
            "amount": float(transaction.amount),
            "description": transaction.description or "Transfer",
            "executed_by": current_user["user_id"],
            "created_at": datetime.now().isoformat()
        }
        
        transaction_record = supabase.table("transaction").insert(transaction_data).execute()

        return {
            "status": "success",
            "new_balance": new_sender_balance,
            "transaction_id": transaction_record.data[0]["id"]
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(500, detail={
            "error": "transfer_failed",
            "message": str(e)
        })


@app.post("/loans/apply")
def apply_loan(application: LoanApplication):
    """Process new loan application"""
    try:
        account = supabase.table("account").select("id").eq("id", application.account_id).execute()
        if not account.data:
            raise HTTPException(404, detail={"error": "account_not_found", "account_id": application.account_id})

        loan_type = supabase.table("loan_type").select("*").eq("id", application.loan_type_id).execute()
        if not loan_type.data:
            raise HTTPException(404, detail={"error": "loan_type_not_found", "loan_type_id": application.loan_type_id})
        
        loan_type = loan_type.data[0]
        
        loan_data = {
            "account_id": application.account_id,
            "loan_type_id": application.loan_type_id,
            "start_date": datetime.now().date().isoformat(),
            "due_date": application.due_date.isoformat() if hasattr(application.due_date, 'isoformat') else application.due_date,
            "amount_paid": application.amount_paid or 0.0
        }
        
        loan_record = supabase.table("loan").insert(loan_data).execute()
        
        return {
            "status": "approved",
            "loan_id": loan_record.data[0]["id"],
            "details": {
                "loan_type": loan_type["type"],
                "interest_rate": loan_type["base_interest_rate"],
                "due_date": loan_data["due_date"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail={
            "error": "loan_processing_failed",
            "message": str(e)
        })

@app.put("/cards/toggle-block")
async def toggle_card_block(
    is_blocked: bool = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Toggle blocking status for the authenticated user's card"""
    try:
        card_id = current_user["linked_customer_id"]
        
        card_response = supabase.table("card") \
            .select("is_blocked") \
            .eq("id", card_id) \
            .execute()

        if not card_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No card found for your account"
            )

        current_status = card_response.data[0]["is_blocked"]

        if current_status == is_blocked:
            return {
                "status": "no_change",
                "card_id": card_id,
                "current_status": current_status,
                "message": f"Card is already {'blocked' if is_blocked else 'active'}"
            }

        supabase.table("card") \
            .update({"is_blocked": is_blocked}) \
            .eq("id", card_id) \
            .execute()

        return {
            "status": "success",
            "card_id": card_id,
            "old_status": current_status,
            "new_status": is_blocked,
            "message": f"Card successfully {'blocked' if is_blocked else 'unblocked'}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating card status: {str(e)}"
        )

@app.get("/accounts/statement")
async def generate_statement(
    current_user: dict = Depends(get_current_user)
):
    """Generate full transaction history for authenticated user's account"""
    try:

        account_response = supabase.table("account") \
            .select("id, balance") \
            .eq("customer_id", current_user["linked_customer_id"]) \
            .execute()
        
        if not account_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found for this user"
            )
        
        account_id = account_response.data[0]["id"]
        balance = account_response.data[0]["balance"]

 
        transactions = supabase.table("transaction") \
            .select("*") \
            .or_(f"from_account.eq.{account_id},to_account.eq.{account_id}") \
            .order("created_at", desc=True) \
            .execute()


        formatted_transactions = []
        for t in transactions.data:
            formatted_transactions.append({
                "id": t["id"],
                "date": t["created_at"],
                "amount": t["amount"],
                "type": "withdrawal" if t["from_account"] == account_id else "deposit",
                "description": t["description"],
                "related_account": t["to_account"] if t["from_account"] == account_id else t["from_account"]
            })


        first_date = transactions.data[-1]["created_at"] if transactions.data else "N/A"
        last_date = transactions.data[0]["created_at"] if transactions.data else "N/A"

        return {
            "account_id": account_id,
            "customer_id": current_user["linked_customer_id"],
            "period": "All transactions", 
            "current_balance": balance,
            "transaction_count": len(transactions.data),
            "transactions": formatted_transactions
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating statement: {str(e)}"
        )

@app.get("/health")
async def health_check():
    try:
        supabase.table("account").select("id").limit(1).execute()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    



@app.get("/test")
def test_endpoint():
    return {"message": "API is working"}


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/auth/login")
async def login(user: UserLogin):
    authenticated_user = await authenticate_user(user.email, user.password)
    if not authenticated_user:
        raise HTTPException(401, "Invalid credentials")
    
    token_data = {
        "sub": user.email,
        "role": authenticated_user["role"],
        "user_id": authenticated_user["user_id"],
        "linked_customer_id": authenticated_user.get("linked_customer_id"), 
        "linked_employee_id": authenticated_user.get("linked_employee_id")  
    }
    token = create_access_token(token_data)
    supabase.table("user_authentication").update({
        "last_login": datetime.now().isoformat()
    }).eq("user_id", authenticated_user["user_id"]).execute()

    return {"access_token": token, "token_type": "bearer"}






async def authenticate_user(email: str, password: str):
    """Authentication function compatible with your 'user_id' column"""
    user = supabase.table("user_authentication") \
        .select("user_id, email, role, password, linked_customer_id, linked_employee_id") \
        .eq("email", email) \
        .maybe_single() \
        .execute()
    
    if not user.data or user.data["password"] != password:
        return False
        
    return {
        "email": user.data["email"],
        "role": user.data["role"],
        "user_id": user.data["user_id"], 
        "linked_customer_id": user.data.get("linked_customer_id"),
        "linked_employee_id": user.data.get("linked_employee_id")
    }




@app.post("/admin/employees")
async def create_employee(
    employee: EmployeeCreate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Only admin can create employees")

    try:
        existing_user = supabase.table("user_authentication") \
            .select("user_id") \
            .eq("email", employee.email) \
            .execute()
        
        if existing_user.data:
            raise HTTPException(400, "Email already exists")

        emp_data = {
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "position": employee.position,
            "department_id": None, 
            "hire_date": datetime.now().date().isoformat()
        }
        new_emp = supabase.table("employee").insert(emp_data).execute()
        emp_id = new_emp.data[0]["employee_id"]


        user_data = {
            "email": employee.email,
            "password": employee.password,
            "role": "employee",
            "linked_employee_id": emp_id,
            "user_id": emp_id  
        }
        supabase.table("user_authentication").insert(user_data).execute()

        return {"status": "success", "employee_id": emp_id}

    except Exception as e:
        raise HTTPException(500, detail=str(e))
    


@app.post("/customers")
async def create_customer(
    customer: CustomerCreate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ["admin", "employee"]:
        raise HTTPException(403, "Only staff can create customers")

    try:

        existing_user = supabase.table("user_authentication") \
            .select("user_id") \
            .eq("email", customer.email) \
            .execute()
        
        if existing_user.data:
            raise HTTPException(400, "Email already exists")


        cust_data = {
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "date_of_birth": customer.date_of_birth,
            "gender": customer.gender
        }
        new_cust = supabase.table("customer").insert(cust_data).execute()
        cust_id = new_cust.data[0]["id"]


        account_data = {
            "id": cust_id,
            "customer_id": cust_id,
            "balance": 0.0,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("account").insert(account_data).execute()


        user_data = {
            "email": customer.email,
            "password": customer.password,
            "role": "customer",
            "linked_customer_id": cust_id,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("user_authentication").insert(user_data).execute()

        return {
            "status": "success",
            "customer_id": cust_id,
            "message": "Customer created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.delete("/admin/employees/{employee_id}")
async def delete_employee(
    employee_id: int,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete employees")
    
    try:

        emp_delete = supabase.table("employee").delete().eq("employee_id", employee_id).execute()
        if not emp_delete.data:
            raise HTTPException(404, "Employee not found")
        
        supabase.table("user_authentication").delete().eq("linked_employee_id", employee_id).execute()
        
        return {"status": "success", "message": "Employee deleted"}
    
    except Exception as e:
        raise HTTPException(500, detail=str(e))
    

@app.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: int,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ["admin", "employee"]:
        raise HTTPException(403, "Only staff can delete customers")
    
    try:

        cust_delete = supabase.table("customer").delete().eq("id", customer_id).execute()
        if not cust_delete.data:
            raise HTTPException(404, "Customer not found")
        

        supabase.table("account").delete().eq("customer_id", customer_id).execute()
        
        supabase.table("card").delete().eq("id", customer_id).execute()  
        
        supabase.table("user_authentication").delete().eq("linked_customer_id", customer_id).execute()
        
        return {"status": "success", "message": "Customer deleted"}
    
    except Exception as e:
        raise HTTPException(500, detail=str(e))
