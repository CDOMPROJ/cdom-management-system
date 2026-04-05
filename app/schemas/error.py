from pydantic import BaseModel

class ErrorResponse(BaseModel):
    """Standardized error response used across all endpoints."""
    detail: str
    code: str = "error"
    timestamp: str = None