from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from wasabot.api.webhook import router as webhook_router

app = FastAPI()

static_dir = Path(__file__).parent.parent / "static"
site_html = Path(__file__).parent.parent / "site" / "index.html"

app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(webhook_router)

@app.get("/", response_class=HTMLResponse)
async def read_root() -> HTMLResponse:
    with site_html.open() as f:
        return HTMLResponse(content=f.read(), status_code=200)
