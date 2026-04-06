# ==========================================
# CDOM SecurityPatch – Revoked Token Model
# ==========================================
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.all_models import Base
import uuid

class RevokedToken(Base):
    # ==========================================
    # Table Definition
    # ==========================================
    __tablename__ = "revoked_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    jti = Column(String, unique=True, index=True, nullable=False)          # JWT ID – unique per token
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)                         # When the token would have expired anyway
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    reason = Column(String, nullable=True)                                # e.g. "logout", "password_change", "mfa_reset"

    # ==========================================
    # Relationships
    # ==========================================
    user = relationship("User", back_populates="revoked_tokens")

    def __repr__(self):
        return f"<RevokedToken jti={self.jti} user_id={self.user_id} reason={self.reason}>"