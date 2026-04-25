"""
Playwright subprocess: handles DeepSeek login & cookie/token capture.
Called from the Jupyter notebook to avoid event loop conflicts.

Usage: python pw_login.py <cookie_file> <login_timeout_sec> <page_timeout_ms>
Output: prints "RESULT:{json}" to stdout on success.
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

DEEPSEEK_BASE_URL = "https://chat.deepseek.com"
DEEPSEEK_LOGIN_URL = "https://chat.deepseek.com/sign_in"
COOKIE_FILE = Path(sys.argv[1])
LOGIN_TIMEOUT = int(sys.argv[2])
PAGE_TIMEOUT = int(sys.argv[3])


def capture_auth_token(page):
    captured = {}

    def on_request(request):
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and "api" in request.url:
            captured["token"] = auth.split("Bearer ", 1)[1]

    page.on("request", on_request)
    page.goto(DEEPSEEK_BASE_URL, timeout=PAGE_TIMEOUT)
    page.wait_for_load_state("networkidle", timeout=15000)
    page.remove_listener("request", on_request)
    return captured.get("token")


def validate_and_reuse(pw, cookies):
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()
    try:
        page.goto(DEEPSEEK_BASE_URL, timeout=PAGE_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=15000)
        url = page.url
        if "sign_in" in url or "login" in url:
            page.close()
            browser.close()
            return None  # cookies expired
        token = capture_auth_token(page)
        page.close()
        browser.close()
        return cookies, token
    except Exception:
        page.close()
        browser.close()
        return None


def manual_login(pw):
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(DEEPSEEK_LOGIN_URL, timeout=PAGE_TIMEOUT)
    print("WAITING_FOR_LOGIN", flush=True)
    try:
        # Wait until we land back on chat.deepseek.com (not Google OAuth or login page)
        page.wait_for_url(
            lambda url: "chat.deepseek.com" in url and "/sign_in" not in url,
            timeout=LOGIN_TIMEOUT * 1000,
        )
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        browser.close()
        print(json.dumps({"error": "Login timed out"}))
        sys.exit(1)
    token = capture_auth_token(page)
    cookies = context.cookies()
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    browser.close()
    return cookies, token


if __name__ == "__main__":
    with sync_playwright() as pw:
        saved = None
        if COOKIE_FILE.exists():
            with open(COOKIE_FILE) as f:
                saved = json.load(f)

        result = None
        if saved:
            result = validate_and_reuse(pw, saved)

        if result is None:
            result = manual_login(pw)

        cookies, token = result
        print("RESULT:" + json.dumps({"token": token, "cookie_count": len(cookies)}))
