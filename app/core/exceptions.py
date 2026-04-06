from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

class CDOMError(Exception):
    """Base exception for all CDOM business errors."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code

async def cdom_exception_handler(request: Request, exc: CDOMError):
    logger.error(f"CDOMError: {exc.message} | Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "CDOM Business Error",
            "detail": exc.message,
            "path": request.url.path,
            "timestamp": "auto"
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"ValidationError: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "path": request.url.path
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please contact the Chancery.",
            "path": request.url.path
        }
    )

def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(CDOMError, cdom_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)