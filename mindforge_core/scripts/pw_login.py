"""
Playwright subprocess: handles DeepSeek login & cookie/token capture.
Called by stage 1 to avoid event loop conflicts.

Uses a persistent Chrome profile so login state survives across runs.
Google OAuth works because it's a real Chrome profile, not automation-detected.

Usage: python pw_login.py <cookie_file> <login_timeout_sec> <page_timeout_ms>
Output: prints "RESULT:{json}" to stdout on success.
"""
import json
import sys
import time as _time
from pathlib import Path
from playwright.sync_api import sync_playwright

DEEPSEEK_BASE_URL = "https://chat.deepseek.com"
DEEPSEEK_LOGIN_URL = "https://chat.deepseek.com/sign_in"
COOKIE_FILE = Path(sys.argv[1])
LOGIN_TIMEOUT = int(sys.argv[2])
PAGE_TIMEOUT = int(sys.argv[3])

# Persistent browser profile directory (next to cookie file)
PROFILE_DIR = COOKIE_FILE.parent / ".chrome_profile"


def is_on_chat_page(url):
    """True only when URL is the main chat page, not an auth/login redirect."""
    auth_paths = ("/sign_in", "/login", "/auth", "/callback", "/oauth", "/sso")
    return "chat.deepseek.com" in url and all(p not in url for p in auth_paths)


def capture_auth_token(page):
    """Intercept API requests to capture the Authorization bearer token."""
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


def wait_for_login(page):
    """Poll until the page URL stabilizes on the chat page for 3 seconds."""
    deadline = _time.time() + LOGIN_TIMEOUT
    stable_since = None

    while _time.time() < deadline:
        try:
            current_url = page.url
        except Exception:
            # Navigation in progress — just wait and retry, don't give up
            stable_since = None
            _time.sleep(0.5)
            continue

        if is_on_chat_page(current_url):
            if stable_since is None:
                stable_since = _time.time()
            elif _time.time() - stable_since >= 3:
                return True
        else:
            stable_since = None
        _time.sleep(0.5)

    return False


if __name__ == "__main__":
    with sync_playwright() as pw:
        # Use persistent context — this creates a real Chrome profile that
        # remembers login state, cookies, localStorage across runs.
        # Google OAuth works because it's indistinguishable from a real user.
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            accept_downloads=False,
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Navigate to DeepSeek
        page.goto(DEEPSEEK_BASE_URL, timeout=PAGE_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=15000)

        # Check if we're already logged in (persistent profile may have session)
        if is_on_chat_page(page.url):
            print("SESSION_REUSED", flush=True)
        else:
            # Need to log in — navigate to login page
            page.goto(DEEPSEEK_LOGIN_URL, timeout=PAGE_TIMEOUT)
            print("WAITING_FOR_LOGIN", flush=True)
            print("Please log in via Google or any other method.", flush=True)

            if not wait_for_login(page):
                context.close()
                print(json.dumps({"error": "Login timed out"}))
                sys.exit(1)

        # Capture auth token
        page.wait_for_load_state("networkidle", timeout=15000)
        token = capture_auth_token(page)

        # Save cookies for the requests.Session in the notebook
        cookies = context.cookies()
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f, indent=2)

        context.close()
        print("RESULT:" + json.dumps({"token": token, "cookie_count": len(cookies)}))
