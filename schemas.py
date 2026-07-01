# Pydantic schemas — 3 distinct shapes for 3 purposes
from pydantic import BaseModel
from typing import Optional

# Shared fields (base class)
class ItemBase(BaseModel):
    name: str;  description: Optional[str] = None
    price: int; is_active: bool = True

# POST body — no id yet (DB assigns it)
class ItemCreate(ItemBase): pass

# PUT body — every field optional for partial updates
class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    is_active: Optional[bool] = None

# Response — adds id, reads ORM objects directly
class ItemResponse(ItemBase):
    id: int
    class Config:
        from_attributes = True  # Pydantic v2

# RAG Recommendation Response
class RecommendationResponse(BaseModel):
    query: str
    retrieved_items: list[ItemResponse]
    prompt_sent: str
    recommendation: str