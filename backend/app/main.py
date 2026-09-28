import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.data.freshness import run_watch_check
from backend.app.settings import get_settings

load_dotenv()
settings = get_settings()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    async def _daily():
        await asyncio.sleep(8)
        while True:
            try:
                await run_watch_check(get_settings().output_dir)
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(24 * 3600)

    task = asyncio.create_task(_daily())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Aurelia Investments", version="1.0.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        index = frontend_dist / "index.html"
        file_path = frontend_dist / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(index)
else:

    @app.get("/")
    async def root():
        return {
            "app": "Aurelia Investments",
            "ok": True,
            "ui": "http://localhost:5173",
            "health": "/api/health",
            "docs": "/docs",
        }
