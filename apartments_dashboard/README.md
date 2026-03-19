# Apartments Dashboard (MVP)

Web+CLI dashboard for daily apartment operations:
- check-ins per day
- check-outs (cleanings) per day
- potential check-outs for idle days

## Files

- `core.py` - shared business logic (config loading, iCal parsing, stats)
- `dashboard.py` - CLI output
- `app.py` - FastAPI web app
- `templates/index.html` - web page
- `dashboard_config.json` - apartments and iCal URLs
- `run_dashboard.bat` - CLI run
- `run_web.bat` - web run

## Install

```bash
python -m pip install -r requirements.txt
```

## Run CLI

```bat
run_dashboard.bat
```

Custom range:

```bash
python dashboard.py --days 30 --start-date 2026-03-20
```

## Run Web

```bat
run_web.bat
```

Open:
- `http://127.0.0.1:8080/`
- API: `http://127.0.0.1:8080/api/dashboard?start_date=2026-03-20&days=21`

## Config

`dashboard_config.json` supports multiple apartments:

```json
{
  "apartments": [
    {
      "name": "Ap1",
      "ical_urls": ["booking_url", "airbnb_url"]
    },
    {
      "name": "Ap2",
      "ical_urls": ["booking_url_2", "airbnb_url_2"]
    }
  ],
  "request_timeout_seconds": 20
}
```

## Potential check-outs logic

For each apartment and day:
- no real check-out on that day
- apartment is idle today
- apartment was idle yesterday

Then this day is counted as a potential check-out day.
