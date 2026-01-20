from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    type: str  # "lost" or "found"
    location: Optional[str] = None

class ItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    type: str
    location: Optional[str] = None
    created_at: datetime

class MatchOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    type: str
    location: Optional[str]
    score: float