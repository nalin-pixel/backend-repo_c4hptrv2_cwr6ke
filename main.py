import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="SocialHub Pro Edition (FastAPI)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------
# Utility & Auth
# -----------------

class SignupBody(BaseModel):
    name: str
    email: str
    password: str

class LoginBody(BaseModel):
    email: str
    password: str

class LinkAccountBody(BaseModel):
    platform: str
    username: str

class UploadBody(BaseModel):
    media_type: str  # video | image | text
    caption: Optional[str] = None
    platforms: List[str]

class ProductBody(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    product_type: str  # digital | physical | service
    status: str = "active"

class OrderBody(BaseModel):
    product_id: str
    buyer_email: str

class AiEditBody(BaseModel):
    source_url: Optional[str] = None
    operations: List[str] = []

PLATFORM_LIMITS = {
    "free": 4,
    "mid_pro": 16,
    "pro": 50,
    "ultra_pro": None,  # unlimited
}

PLATFORMS = [
    {"key": "instagram", "name": "Instagram", "url": "https://instagram.com"},
    {"key": "facebook", "name": "Facebook", "url": "https://facebook.com"},
    {"key": "youtube", "name": "YouTube", "url": "https://youtube.com"},
    {"key": "tiktok", "name": "TikTok", "url": "https://www.tiktok.com"},
    {"key": "x", "name": "X", "url": "https://x.com"},
    {"key": "threads", "name": "Threads", "url": "https://threads.net"},
    {"key": "linkedin", "name": "LinkedIn", "url": "https://linkedin.com"},
    {"key": "pinterest", "name": "Pinterest", "url": "https://pinterest.com"},
    {"key": "snapchat", "name": "Snapchat", "url": "https://www.snapchat.com"},
    {"key": "reddit", "name": "Reddit", "url": "https://reddit.com"},
    {"key": "twitch", "name": "Twitch", "url": "https://twitch.tv"},
    {"key": "discord", "name": "Discord", "url": "https://discord.com"},
    {"key": "spotify", "name": "Spotify", "url": "https://spotify.com"},
    {"key": "medium", "name": "Medium", "url": "https://medium.com"},
    {"key": "substack", "name": "Substack", "url": "https://substack.com"},
    {"key": "vimeo", "name": "Vimeo", "url": "https://vimeo.com"},
    {"key": "dribbble", "name": "Dribbble", "url": "https://dribbble.com"},
    {"key": "behance", "name": "Behance", "url": "https://behance.net"},
    {"key": "producthunt", "name": "Product Hunt", "url": "https://www.producthunt.com"},
    {"key": "hackernews", "name": "Hacker News", "url": "https://news.ycombinator.com"},
    {"key": "gumroad", "name": "Gumroad", "url": "https://gumroad.com"},
    {"key": "shopify", "name": "Shopify", "url": "https://shopify.com"},
    {"key": "amazon", "name": "Amazon", "url": "https://amazon.com"},
    {"key": "primevideo", "name": "Prime Video", "url": "https://primevideo.com"},
    {"key": "bluesky", "name": "Bluesky", "url": "https://bsky.app"},
    {"key": "mastodon", "name": "Mastodon", "url": "https://joinmastodon.org"},
    {"key": "quora", "name": "Quora", "url": "https://quora.com"},
    {"key": "vk", "name": "VK", "url": "https://vk.com"},
    {"key": "ok", "name": "Odnoklassniki", "url": "https://ok.ru"},
    {"key": "wechat", "name": "WeChat", "url": "https://www.wechat.com"},
    {"key": "weibo", "name": "Weibo", "url": "https://weibo.com"},
    {"key": "kakaotalk", "name": "KakaoTalk", "url": "https://www.kakaocorp.com"},
    {"key": "line", "name": "LINE", "url": "https://line.me"},
    {"key": "telegram", "name": "Telegram", "url": "https://telegram.org"},
    {"key": "signal", "name": "Signal", "url": "https://signal.org"},
    {"key": "whatsapp", "name": "WhatsApp", "url": "https://whatsapp.com"},
    {"key": "rss", "name": "RSS", "url": "https://rss.com"},
    {"key": "snapchat_spotlight", "name": "Snap Spotlight", "url": "https://www.snapchat.com/spotlight"},
    {"key": "notion", "name": "Notion", "url": "https://notion.so"},
    {"key": "figma", "name": "Figma", "url": "https://figma.com"},
    {"key": "devto", "name": "Dev.to", "url": "https://dev.to"},
    {"key": "hashnode", "name": "Hashnode", "url": "https://hashnode.com"},
    {"key": "codepen", "name": "CodePen", "url": "https://codepen.io"},
    {"key": "codesandbox", "name": "CodeSandbox", "url": "https://codesandbox.io"},
    {"key": "replit", "name": "Replit", "url": "https://replit.com"},
    {"key": "kaggle", "name": "Kaggle", "url": "https://kaggle.com"},
    {"key": "drone", "name": "Drone", "url": "https://drone.io"},
    {"key": "gitlab", "name": "GitLab", "url": "https://gitlab.com"},
    {"key": "github", "name": "GitHub", "url": "https://github.com"},
    {"key": "bitbucket", "name": "Bitbucket", "url": "https://bitbucket.org"},
    {"key": "stackoverflow", "name": "Stack Overflow", "url": "https://stackoverflow.com"},
]


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db["session"].insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    return token


def get_user_from_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = parts[1]
    sess = db["session"].find_one({"token": token})
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid token")
    if sess.get("expires_at") and sess["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = db["user"].find_one({"_id": ObjectId(sess["user_id"])})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.get("/")
def root():
    return {"message": "SocialHub Pro Edition backend running"}

@app.get("/platforms")
def get_platforms():
    return {"platforms": PLATFORMS}

# ---------------
# Auth
# ---------------

@app.post("/auth/signup")
def signup(body: SignupBody):
    existing = db["user"].find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = create_document("user", {
        "name": body.name,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "plan": "free",
        "avatar_url": None,
    })
    token = create_session(user_id)
    return {"token": token, "user": {"id": user_id, "name": body.name, "email": body.email, "plan": "free"}}

@app.post("/auth/login")
def login(body: LoginBody):
    user = db["user"].find_one({"email": body.email})
    if not user or user.get("password_hash") != hash_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session(str(user["_id"]))
    return {"token": token, "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"], "plan": user.get("plan", "free")}}

@app.get("/me")
def me(user=Depends(get_user_from_token)):
    return {"id": str(user["_id"]), "name": user["name"], "email": user["email"], "plan": user.get("plan", "free")}

# ---------------
# Social Accounts
# ---------------

@app.get("/accounts")
def list_accounts(user=Depends(get_user_from_token)):
    items = list(db["socialaccount"].find({"user_id": str(user["_id"])}))
    for it in items:
        it["id"] = str(it["_id"])  # expose id
        del it["_id"]
    return {"accounts": items}

@app.post("/accounts")
def link_account(body: LinkAccountBody, user=Depends(get_user_from_token)):
    # Simulate OAuth linking by storing username + platform
    acc_id = create_document("socialaccount", {
        "user_id": str(user["_id"]),
        "platform": body.platform,
        "username": body.username,
        "followers": 0,
        "access_token": None,
        "last_sync": None,
        "status": "connected",
    })
    return {"id": acc_id}

# ---------------
# Uploads & Limits
# ---------------

def get_daily_count(user_id: str) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return db["uploadlog"].count_documents({"user_id": user_id, "created_at": {"$gte": start, "$lt": end}})

@app.get("/uploads/stats")
def uploads_stats(user=Depends(get_user_from_token)):
    plan = user.get("plan", "free")
    limit = PLATFORM_LIMITS.get(plan)
    used = get_daily_count(str(user["_id"]))
    return {"plan": plan, "limit": limit, "used": used}

@app.post("/upload")
def upload(body: UploadBody, user=Depends(get_user_from_token)):
    plan = user.get("plan", "free")
    limit = PLATFORM_LIMITS.get(plan)
    used = get_daily_count(str(user["_id"]))
    to_add = len(body.platforms)
    if limit is not None and used + to_add > limit:
        raise HTTPException(status_code=429, detail=f"Daily limit exceeded. {used}/{limit} used.")
    # Simulate queuing a job per platform
    log_id = create_document("uploadlog", {
        "user_id": str(user["_id"]),
        "media_type": body.media_type,
        "caption": body.caption,
        "platforms": body.platforms,
        "status": "queued",
        "error": None,
    })
    return {"status": "queued", "log_id": log_id}

# ---------------
# Products & Orders
# ---------------

@app.get("/products")
def list_products(user=Depends(get_user_from_token)):
    items = list(db["product"].find({"user_id": str(user["_id"])}))
    results = []
    for it in items:
        results.append({
            "id": str(it["_id"]),
            "title": it.get("title"),
            "description": it.get("description"),
            "price": it.get("price", 0),
            "product_type": it.get("product_type"),
            "status": it.get("status", "active"),
        })
    return {"products": results}

@app.post("/products")
def create_product(body: ProductBody, user=Depends(get_user_from_token)):
    pid = create_document("product", {
        "title": body.title,
        "description": body.description,
        "price": body.price,
        "product_type": body.product_type,
        "status": body.status,
        "user_id": str(user["_id"]),
    })
    return {"id": pid}

@app.put("/products/{product_id}")
def update_product(product_id: str, body: ProductBody, user=Depends(get_user_from_token)):
    prod = db["product"].find_one({"_id": ObjectId(product_id), "user_id": str(user["_id"])})
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    db["product"].update_one({"_id": ObjectId(product_id)}, {"$set": {
        "title": body.title,
        "description": body.description,
        "price": body.price,
        "product_type": body.product_type,
        "status": body.status,
        "updated_at": datetime.now(timezone.utc)
    }})
    return {"ok": True}

@app.delete("/products/{product_id}")
def delete_product(product_id: str, user=Depends(get_user_from_token)):
    db["product"].delete_one({"_id": ObjectId(product_id), "user_id": str(user["_id"])})
    return {"ok": True}

@app.post("/orders")
def create_order(body: OrderBody, user=Depends(get_user_from_token)):
    prod = db["product"].find_one({"_id": ObjectId(body.product_id), "user_id": str(user["_id"])})
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    order_id = create_document("order", {
        "user_id": str(user["_id"]),
        "product_id": body.product_id,
        "buyer_email": body.buyer_email,
        "amount": prod.get("price", 0),
        "currency": "USD",
        "status": "paid",
    })
    return {"id": order_id, "status": "paid"}

# ---------------
# AI Edit (Ultra Pro only)
# ---------------

@app.post("/ai/edit")
def ai_edit(body: AiEditBody, user=Depends(get_user_from_token)):
    if user.get("plan", "free") != "ultra_pro":
        raise HTTPException(status_code=403, detail="AI video editing is available for Ultra Pro only")
    # Simulate AI edit job
    job_id = create_document("aijob", {
        "user_id": str(user["_id"]),
        "source_url": body.source_url,
        "operations": body.operations,
        "status": "processing",
    })
    return {"job_id": job_id, "status": "processing"}

# ---------------
# Diagnostics
# ---------------

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:20]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
