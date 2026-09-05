from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import auth
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.database.seed import seed_authority_officer, seed_demonstration_cases
from app.database.session import AsyncSessionLocal, check_database_connection, engine
from app.models.base import Base
from app.schemas.health import DatabaseHealth, HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    # Ensure tables exist and seed initial authority officer if database is reachable
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncSessionLocal() as session:
            officer = await seed_authority_officer(session)
            await seed_demonstration_cases(session, officer)
    except Exception as exc:
        # If external PostgreSQL is currently offline, don't crash startup; health check will report status
        pass
    yield


def create_application() -> FastAPI:
    """Application factory for DRISHTI backend service."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
        docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
        redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
        description=(
            "DRISHTI: AI-Powered Product Compliance Risk Intelligence System. "
            "Authority-facing surveillance and regulatory intelligence platform."
        ),
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized error handling
    register_error_handlers(app)

    # Root health check endpoint
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Root Health Check",
    )
    async def root_health(check_db: bool = Query(default=True)):
        db_health = None
        if check_db:
            db_result = await check_database_connection()
            db_health = DatabaseHealth(
                status=db_result["status"],
                latency_ms=db_result["latency_ms"],
                error=db_result["error"],
            )

        return HealthResponse(
            status="ok",
            project=settings.PROJECT_NAME,
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            timestamp=datetime.now(timezone.utc),
            database=db_health,
        )

    # Mount auth router at root level (/auth/login, /auth/logout, /auth/me)
    app.include_router(auth.router)

    # Register API v1 routes (/api/v1/...)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Mount static files for stored evidence and packaging images
    import os
    from fastapi.staticfiles import StaticFiles
    from app.core.storage import UPLOAD_DIR

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    return app


app = create_application()
