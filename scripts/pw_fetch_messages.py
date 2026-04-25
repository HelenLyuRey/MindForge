"""
Playwright subprocess: scrapes messages from a single conversation page.
Called from the Jupyter notebook as a fallback when the API approach fails.

Usage: python pw_fetch_messages.py <cookie_file> <conversation_url> <page_timeout_ms>
Output: prints "RESULT:{json}" to stdout on success.
"""
import json
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIE_FILE = Path(sys.argv[1])
CONV_URL = sys.argv[2]
PAGE_TIMEOUT = int(sys.argv[3])

with open(COOKIE_FILE) as f:
    cookies = json.load(f)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()
    page.goto(CONV_URL, timeout=PAGE_TIMEOUT)
    page.wait_for_load_state("networkidle", timeout=20000)

    # Wait for messages to render
    page.wait_for_timeout(2000)

    messages = []

    # Try to find message containers — common patterns in chat UIs
    msg_selectors = [
        "[class*='message']",
        "[class*='chat-message']",
        "[data-role]",
        ".markdown",
    ]

    msg_elements = []
    for sel in msg_selectors:
        elements = page.locator(sel).all()
        if len(elements) >= 2:
            msg_elements = elements
            break

    if not msg_elements:
        msg_elements = page.locator(
            "main div[class*='msg'], main div[class*='content']"
        ).all()

    for el in msg_elements:
        # Determine role
        role_attr = el.get_attribute("data-role") or ""
        classes = el.get_attribute("class") or ""

        if "user" in role_attr.lower() or "user" in classes.lower():
            role = "user"
        elif (
            "assistant" in role_attr.lower()
            or "bot" in classes.lower()
            or "assistant" in classes.lower()
        ):
            role = "assistant"
        else:
            continue

        # Get HTML content and skip thinking blocks
        html = el.inner_html()
        html = re.sub(r"<details[^>]*>.*?</details>", "", html, flags=re.DOTALL)
        html = re.sub(
            r'<div[^>]*class="[^"]*think[^"]*"[^>]*>.*?</div>',
            "",
            html,
            flags=re.DOTALL,
        )

        text = el.inner_text().strip()

        if text:
            messages.append({"role": role, "content": text, "html": html})

    browser.close()
    print("RESULT:" + json.dumps(messages))
