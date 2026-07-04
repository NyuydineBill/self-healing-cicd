from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nyuydine.api.routes import health, repairs, webhooks
from nyuydine.config import get_platform_settings
from nyuydine.db.session import init_db


def create_app() -> FastAPI:
    settings = get_platform_settings()
    app = FastAPI(
        title="Nyuydine Platform API",
        description="Phase 1 — GitHub Reliability Engine",
        version="0.2.0",
    )

    origins = list(settings.cors_origins) or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(repairs.router)
    app.include_router(webhooks.router)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()
