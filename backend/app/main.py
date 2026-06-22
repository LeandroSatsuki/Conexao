from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes_connections import router as connections_router
from app.api.v1.routes_connectors import router as connectors_router
from app.api.v1.routes_flows import router as flows_router
from app.api.v1.routes_health import router as health_router
from app.api.v1.routes_jobs import router as jobs_router
from app.api.v1.routes_logs import router as logs_router
from app.api.v1.routes_mappings import router as mappings_router
from app.api.v1.routes_tenants import router as tenants_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version="0.1.0")

    origins = settings.parsed_cors_origins
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins if origins != ["*"] else ["*"],
            allow_credentials=origins != ["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(tenants_router, prefix=settings.api_v1_prefix)
    app.include_router(connectors_router, prefix=settings.api_v1_prefix)
    app.include_router(connections_router, prefix=settings.api_v1_prefix)
    app.include_router(flows_router, prefix=settings.api_v1_prefix)
    app.include_router(mappings_router, prefix=settings.api_v1_prefix)
    app.include_router(logs_router, prefix=settings.api_v1_prefix)
    app.include_router(jobs_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
