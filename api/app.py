from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, nodes, overlays, scenarios


def create_app() -> FastAPI:
    app = FastAPI(title="Nile Digital Twin API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(nodes.router)
    app.include_router(overlays.router)
    app.include_router(scenarios.router)
    return app


app = create_app()
