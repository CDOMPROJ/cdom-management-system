# ==========================================
# CDOM SecurityPatch – User Model Update
# ==========================================
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.all_models import Base
import uuid

class User(Base):
    # ==========================================
    # Table Definition
    # ==========================================
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    role = Column(String, nullable=False)                     # Bishop, DeaneryAdmin, ParishPriest, etc.
    parish_id = Column(UUID(as_uuid=True), nullable=True)

    # ==========================================
    # SecurityPatch: Token Version for "Logout from all devices"
    # ==========================================
    token_version = Column(Integer, default=0, nullable=False)

    # ==========================================
    # Relationships
    # ==========================================
    revoked_tokens = relationship("RevokedToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email} role={self.role}>"