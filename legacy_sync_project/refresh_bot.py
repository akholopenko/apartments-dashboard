import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


CONFIG_PATH = Path("refresh_bot_config.json")
LOG_PATH = Path("refresh_bot.log")
COOLDOWN_STAMP_PATH = Path("refresh_bot_last_run.txt")


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

    logger = logging.getLogger("refresh_bot")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = setup_logging()


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def check_cooldown(cooldown_seconds):
    if cooldown_seconds <= 0:
        return True

    if not COOLDOWN_STAMP_PATH.exists():
        return True

    try:
        last_run = float(COOLDOWN_STAMP_PATH.read_text(encoding="utf-8").strip())
    except Exception:
        return True

    delta = time.time() - last_run
    if delta < cooldown_seconds:
        logger.info("Cooldown active: wait %s more seconds", int(cooldown_seconds - delta))
        return False
    return True


def mark_run():
    COOLDOWN_STAMP_PATH.write_text(str(time.time()), encoding="utf-8")


def first_visible(page, selectors, timeout_ms=2500):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator, selector
        except Exception:
            continue
    return None, None


def try_login(page, config):
    username = os.getenv("BOOKING_USERNAME")
    password = os.getenv("BOOKING_PASSWORD")
    if not username or not password:
        logger.warning("BOOKING_USERNAME or BOOKING_PASSWORD is not set. Skipping automatic login.")
        return False

    selectors = config["selectors"]
    page.goto(config["booking_login_url"], wait_until="domcontentloaded")

    username_input, username_selector = first_visible(page, selectors["username"])
    password_input, password_selector = first_visible(page, selectors["password"])

    if not username_input or not password_input:
        logger.warning("Login form inputs not found.")
        return False

    logger.info("Login form found. Filling credentials.")
    username_input.fill(username)
    password_input.fill(password)

    submit_button, submit_selector = first_visible(page, selectors["submit"])
    if not submit_button:
        logger.warning("Login submit button not found.")
        return False

    logger.info("Submitting login form with selector: %s", submit_selector)
    submit_button.click()
    page.wait_for_timeout(1500)

    manual_2fa_timeout_seconds = int(config.get("manual_2fa_timeout_seconds", 120))
    logger.info("If 2FA is required, complete it in the opened browser (%s sec timeout).", manual_2fa_timeout_seconds)
    page.wait_for_timeout(manual_2fa_timeout_seconds * 1000)
    return True


def run_refresh():
    config = load_config()
    cooldown_seconds = int(config.get("cooldown_seconds", 0))
    if not check_cooldown(cooldown_seconds):
        return 0

    selectors = config["selectors"]
    storage_state_path = config.get("storage_state_path", "booking_storage_state.json")
    screenshot_path = config.get("screenshot_path", "refresh_bot_last.png")
    headless = bool(config.get("headless", False))
    timeout_ms = int(config.get("navigation_timeout_ms", 45000))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        context_kwargs = {}
        if Path(storage_state_path).exists():
            context_kwargs["storage_state"] = storage_state_path

        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            logger.info("Opening Booking connections page.")
            page.goto(config["booking_connections_url"], wait_until="domcontentloaded")

            refresh_button, refresh_selector = first_visible(page, selectors["refresh"], timeout_ms=5000)
            if not refresh_button:
                logger.info("Refresh button not visible. Trying login.")
                try_login(page, config)
                page.goto(config["booking_connections_url"], wait_until="domcontentloaded")
                refresh_button, refresh_selector = first_visible(page, selectors["refresh"], timeout_ms=7000)

            if not refresh_button:
                page.screenshot(path=screenshot_path, full_page=True)
                logger.error("Refresh button not found. Screenshot saved: %s", screenshot_path)
                return 2

            logger.info("Clicking refresh button with selector: %s", refresh_selector)
            refresh_button.click()
            page.wait_for_timeout(2500)

            context.storage_state(path=storage_state_path)
            page.screenshot(path=screenshot_path, full_page=True)
            mark_run()
            logger.info("Refresh action completed. Storage and screenshot saved.")
            return 0

        except PlaywrightTimeoutError:
            page.screenshot(path=screenshot_path, full_page=True)
            logger.exception("Timeout while refreshing Booking connection.")
            return 3
        except Exception:
            page.screenshot(path=screenshot_path, full_page=True)
            logger.exception("Unexpected refresh bot error.")
            return 4
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    raise SystemExit(run_refresh())
