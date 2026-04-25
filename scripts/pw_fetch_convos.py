"""
Playwright subprocess: scrolls sidebar to scrape all conversation entries.
Called from the Jupyter notebook as a fallback when the API approach fails.

Usage: python pw_fetch_convos.py <cookie_file> <page_timeout_ms>
Output: prints "RESULT:{json}" to stdout on success.
"""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIE_FILE = Path(sys.argv[1])
BASE_URL = "https://chat.deepseek.com"
PAGE_TIMEOUT = int(sys.argv[2])

with open(COOKIE_FILE) as f:
    cookies = json.load(f)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()
    page.goto(BASE_URL, timeout=PAGE_TIMEOUT)
    page.wait_for_load_state("networkidle", timeout=15000)

    # Find the sidebar conversation list container
    sidebar = page.locator("nav").first
    if not sidebar.is_visible():
        sidebar = page.locator(
            "[class*='sidebar'], [class*='history'], [class*='conversation-list']"
        ).first

    # Scroll to load all conversations
    prev_count = 0
    for _ in range(100):  # max 100 scroll attempts
        items = page.locator("nav a[href*='/a/'], a[href*='/chat/']").all()
        count = len(items)
        if count == prev_count:
            break
        prev_count = count
        sidebar.evaluate("el => el.scrollTop = el.scrollHeight")
        time.sleep(0.5)

    # Extract conversation data
    conversations = []
    links = page.locator("nav a[href*='/a/'], a[href*='/chat/']").all()
    for link in links:
        href = link.get_attribute("href") or ""
        title = link.inner_text().strip() or "Untitled"
        conv_id = href.rstrip("/").split("/")[-1] if "/" in href else ""
        if conv_id:
            conversations.append({
                "conversation_id": conv_id,
                "original_title": title,
                "url": BASE_URL + href,
            })

    browser.close()
    print("RESULT:" + json.dumps(conversations))
