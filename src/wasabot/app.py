from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from wasabot.api.webhook import router as webhook_router
from wasabot.services.logger import get_logger, setup_logging
from wasabot.services.scheduler import start_scheduler

# Setup logging before anything else
setup_logging()
logger = get_logger(__name__)

app = FastAPI()

static_dir = Path(__file__).parent.parent / "static"
site_html = Path(__file__).parent.parent / "site" / "index.html"

app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(webhook_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Start background scheduler on app startup."""
    logger.info("app_startup_starting")
    start_scheduler()
    logger.info("app_startup_complete")


@app.get("/", response_class=HTMLResponse)
async def read_root() -> HTMLResponse:
    with site_html.open() as f:
        return HTMLResponse(content=f.read(), status_code=200)
