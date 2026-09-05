from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings


class DrishtiException(Exception):
    """Base exception for all domain-level DRISHTI errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


def format_error_response(
    status_code: int,
    error_code: str,
    message: str,
    path: str,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    payload = {
        "status": status_code,
        "error_code": error_code,
        "message": message,
        "path": path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }
    return JSONResponse(status_code=status_code, content=payload)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DrishtiException)
    async def drishti_exception_handler(request: Request, exc: DrishtiException):
        return format_error_response(
            status_code=exc.status_code,
            error_code=exc.code,
            message=exc.message,
            path=str(request.url.path),
            details=exc.details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return format_error_response(
            status_code=exc.status_code,
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            path=str(request.url.path),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return format_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            message="Request body or query parameter validation failed",
            path=str(request.url.path),
            details={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        details = {"type": type(exc).__name__, "message": str(exc)} if settings.DEBUG else {}
        return format_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred",
            path=str(request.url.path),
            details=details,
        )

