from datetime import date
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core import get_dashboard_data


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Apartments Dashboard", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard_api(
    days: int = Query(default=21, ge=1, le=120),
    start_date: str = Query(default=date.today().isoformat()),
):
    data = get_dashboard_data(days=days, start_date=start_date)
    return JSONResponse(data)


@app.get("/", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    days: int = Query(default=21, ge=1, le=120),
    start_date: str = Query(default=date.today().isoformat()),
):
    data = get_dashboard_data(days=days, start_date=start_date)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "days": days,
            "start_date": start_date,
            "rows": data["rows"],
            "warnings": data["warnings"],
        },
    )
