from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import deps
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

    tiles_dir = deps.DATA_DIR / "tiles"
    if tiles_dir.exists():
        app.mount("/tiles", StaticFiles(directory=str(tiles_dir)), name="tiles")

    return app


app = create_app()
