"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password")
    plan: str = Field("free", description="Subscription plan: free | mid_pro | pro | ultra_pro")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")

class SocialAccount(BaseModel):
    user_id: str = Field(..., description="Owner user id (string of ObjectId)")
    platform: str = Field(..., description="Platform key, e.g., instagram, youtube, tiktok, x")
    username: str = Field(..., description="Account username/handle")
    followers: Optional[int] = Field(0, description="Follower count if known")
    access_token: Optional[str] = Field(None, description="OAuth access token or placeholder")
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    status: str = Field("connected", description="connected | error | expired")

class UploadLog(BaseModel):
    user_id: str = Field(..., description="Uploader user id")
    media_type: str = Field(..., description="video | image | text")
    caption: Optional[str] = Field(None)
    platforms: List[str] = Field(default_factory=list)
    status: str = Field("queued", description="queued | posted | failed")
    error: Optional[str] = Field(None)

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    product_type: str = Field(..., description="digital | physical | service")
    status: str = Field("active", description="active | draft | archived")
    user_id: str = Field(..., description="Owner user id")

class Order(BaseModel):
    user_id: str = Field(..., description="Seller user id")
    product_id: str = Field(...)
    buyer_email: str = Field(...)
    amount: float = Field(..., ge=0)
    currency: str = Field("USD")
    status: str = Field("paid", description="paid | pending | failed")
