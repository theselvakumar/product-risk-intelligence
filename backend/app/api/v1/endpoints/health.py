from datetime import datetime, timezone
from fastapi import APIRouter, Query

from app.core.config import settings
from app.database.session import check_database_connection
from app.schemas.health import DatabaseHealth, HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Diagnostic Status",
    description="Returns service availability, timestamp, and optional database connectivity status.",
)
async def get_health(check_db: bool = Query(default=True, description="Whether to probe database connection")):
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
