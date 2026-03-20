from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core import get_dashboard_data


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Apartments Dashboard", version="0.1.0")


def build_month_calendar(rows, month_str):
    month_start = datetime.strptime(month_str + "-01", "%Y-%m-%d").date()
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_days = (next_month - month_start).days

    rows_by_date = {r["date"]: r for r in rows}
    month_rows = []
    for i in range(month_days):
        day = month_start + timedelta(days=i)
        row = rows_by_date.get(day.isoformat())
        if row is None:
            row = {
                "date": day.isoformat(),
                "checkins_count": 0,
                "checkouts_count": 0,
                "potential_count": 0,
            }
        month_rows.append(row)

    first_weekday = month_start.weekday()  # Monday=0
    cells = [None] * first_weekday + month_rows
    while len(cells) % 7 != 0:
        cells.append(None)

    weeks = [cells[i : i + 7] for i in range(0, len(cells), 7)]
    return weeks


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
    mode: str = Query(default="table"),
):
    today_iso = date.today().isoformat()

    if mode not in {"table", "calendar"}:
        mode = "table"

    if mode == "calendar":
        month = start_date[:7]
        month_start = datetime.strptime(month + "-01", "%Y-%m-%d").date()
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        prev_month = (month_start - timedelta(days=1)).replace(day=1)
        month_days = (next_month - month_start).days
        data = get_dashboard_data(days=month_days, start_date=month_start.isoformat())
        calendar_weeks = build_month_calendar(data["rows"], month)
        prev_month_start = prev_month.isoformat()
        next_month_start = next_month.isoformat()
    else:
        month = start_date[:7]
        data = get_dashboard_data(days=days, start_date=start_date)
        calendar_weeks = []
        prev_month_start = ""
        next_month_start = ""

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "days": days,
            "start_date": start_date,
            "month": month,
            "mode": mode,
            "rows": data["rows"],
            "calendar_weeks": calendar_weeks,
            "prev_month_start": prev_month_start,
            "next_month_start": next_month_start,
            "today_iso": today_iso,
            "warnings": data["warnings"],
        },
    )
