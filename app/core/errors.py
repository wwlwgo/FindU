from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass
class ApiError(Exception):
    code: str
    message: str
    status_code: int


def error_response(
    *, code: str, message: str, request_id: str, status_code: int, details: Any | None = None
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message, "requestId": request_id}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        code=exc.code,
        message=exc.message,
        request_id=request.state.request_id,
        status_code=exc.status_code,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        request_id=request.state.request_id,
        status_code=422,
        details=exc.errors(),
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        code, message = "NOT_FOUND", "Resource not found"
    else:
        code, message = "HTTP_ERROR", str(exc.detail)
    return error_response(
        code=code,
        message=message,
        request_id=request.state.request_id,
        status_code=exc.status_code,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        request_id=request.state.request_id,
        status_code=500,
    )

