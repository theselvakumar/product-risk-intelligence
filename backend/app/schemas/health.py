from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: str = Field(..., description="'connected' or 'disconnected'")
    latency_ms: Optional[float] = Field(None, description="Roundtrip query latency in ms")
    error: Optional[str] = Field(None, description="Error detail if disconnected")


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Overall application status")
    project: str = Field(..., description="Project name")
    version: str = Field(..., description="Current deployment version")
    environment: str = Field(..., description="Active environment (development/production)")
    timestamp: datetime = Field(..., description="Current UTC timestamp")
    database: Optional[DatabaseHealth] = Field(None, description="Database connection health check")
