from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.participants import router as participants_router
from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.database import Database
from app.core.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        from app.services.seed import ensure_demo_activity

        ensure_demo_activity(database.session_factory())
        yield
        database.dispose()

    app = FastAPI(title="FindU API", version="0.1.0", lifespan=lifespan)
    app.state.database = database

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = request.headers.get("X-Request-ID", uuid4().hex)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(health_router)
    app.include_router(participants_router)

    return app


app = create_app()
