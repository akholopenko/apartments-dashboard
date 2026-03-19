from datetime import datetime
import time
import os
import logging
from logging.handlers import RotatingFileHandler
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8000
CALENDAR_PATH = "synced_calendar.ics"
LAST_REQUEST_PATH = "last_request.txt"
LOG_PATH = "server.log"

last_calendar_request = 0


def setup_logging():
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=500_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger("server")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = setup_logging()


class CalendarHandler(BaseHTTPRequestHandler):
    def send_text_response(self, status_code, body):
        payload = body.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):

        global last_calendar_request

        user_agent = self.headers.get("User-Agent")

        now = datetime.now().strftime("%H:%M:%S")

        logger.info("[%s] Request from: %s", now, user_agent)
        logger.info("Path: %s", self.path)

        if self.path != "/synced_calendar.ics":
            self.send_text_response(404, "Not Found")
            return

        last_calendar_request = time.time()
        try:
            with open(LAST_REQUEST_PATH, "w", encoding="utf-8") as f:
                f.write(str(last_calendar_request))
        except OSError as error:
            logger.warning("Cannot write last request timestamp: %s", error)

        if not os.path.exists(CALENDAR_PATH):
            self.send_text_response(503, "Calendar is not generated yet")
            return

        try:
            with open(CALENDAR_PATH, "rb") as f:
                data = f.read()
        except OSError as error:
            logger.error("Error reading calendar: %s", error)
            self.send_text_response(500, "Cannot read calendar file")
            return

        logger.info("Calendar requested")
        self.send_response(200)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        if self.path == "/synced_calendar.ics" and os.path.exists(CALENDAR_PATH):
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        self.send_text_response(405, "Method Not Allowed")


server = HTTPServer(("0.0.0.0", PORT), CalendarHandler)

logger.info("Server running on port %s", PORT)

server.serve_forever()
