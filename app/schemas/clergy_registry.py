from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class ClergyRegistryBase(BaseModel):
    category: str
    congregation: Optional[str] = None
    status: str
    current_location: Optional[str] = None
    ministry_category: Optional[str] = None

class ClergyRegistryCreate(ClergyRegistryBase):
    pass

class ClergyRegistryResponse(ClergyRegistryBase):
    id: uuid.UUID
    last_updated: datetime
    updated_by: str

    class Config:
        from_attributes = True