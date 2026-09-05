from fastapi import APIRouter
from app.api.v1.endpoints import auth, cases, health

api_router = APIRouter()

# Register endpoint routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(cases.router)
