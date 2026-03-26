from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Glam Orders API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

security = HTTPBearer()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user = supabase_admin.auth.get_user(token)
        if not user or not user.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class OrderCreate(BaseModel):
    name: str
    insta: Optional[str] = ""
    address: str
    phone: Optional[str] = ""
    pincode: Optional[str] = ""
    product: Optional[str] = ""
    amount: Optional[float] = 0
    weight: Optional[float] = 500
    payment: Optional[str] = "prepaid"
    notes: Optional[str] = ""
    status: Optional[str] = "pending"
    awb: Optional[str] = ""

class OrderUpdate(BaseModel):
    name: Optional[str] = None
    insta: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    pincode: Optional[str] = None
    product: Optional[str] = None
    amount: Optional[float] = None
    weight: Optional[float] = None
    payment: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    awb: Optional[str] = None


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.post("/auth/login")
def login(req: LoginRequest):
    try:
        res = supabase_admin.auth.sign_in_with_password({"email": req.email, "password": req.password})
        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": {"id": res.user.id, "email": res.user.email}
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")


@app.post("/auth/logout")
def logout(user=Depends(get_current_user)):
    return {"message": "Logged out"}


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email}


# ── Order routes ──────────────────────────────────────────────────────────────

@app.get("/orders")
def list_orders(status: Optional[str] = None, search: Optional[str] = None, user=Depends(get_current_user)):
    query = supabase_admin.table("orders").select("*").eq("user_id", user.id).order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    res = query.execute()
    orders = res.data or []
    if search:
        s = search.lower()
        orders = [o for o in orders if s in (o.get("name") or "").lower()
                  or s in (o.get("insta") or "").lower()
                  or s in (o.get("product") or "").lower()]
    return orders


@app.post("/orders", status_code=201)
def create_order(order: OrderCreate, user=Depends(get_current_user)):
    data = order.dict()
    data["user_id"] = user.id
    res = supabase_admin.table("orders").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Failed to create order")
    return res.data[0]


@app.get("/orders/{order_id}")
def get_order(order_id: str, user=Depends(get_current_user)):
    res = supabase_admin.table("orders").select("*").eq("id", order_id).eq("user_id", user.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return res.data[0]


@app.patch("/orders/{order_id}")
def update_order(order_id: str, update: OrderUpdate, user=Depends(get_current_user)):
    data = {k: v for k, v in update.dict().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = supabase_admin.table("orders").update(data).eq("id", order_id).eq("user_id", user.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return res.data[0]


@app.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: str, user=Depends(get_current_user)):
    supabase_admin.table("orders").delete().eq("id", order_id).eq("user_id", user.id).execute()
    return


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/stats")
def get_stats(user=Depends(get_current_user)):
    res = supabase_admin.table("orders").select("*").eq("user_id", user.id).execute()
    orders = res.data or []
    total = len(orders)
    pending = sum(1 for o in orders if o.get("status") == "pending")
    shipped = sum(1 for o in orders if o.get("status") == "shipped")
    revenue = sum(float(o.get("amount") or 0) for o in orders if o.get("status") != "cancelled")
    return {"total": total, "pending": pending, "shipped": shipped, "revenue": revenue}


@app.get("/health")
def health():
    return {"status": "ok"}
