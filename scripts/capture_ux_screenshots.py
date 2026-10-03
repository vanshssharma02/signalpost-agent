#!/usr/bin/env python3
"""capture_ux_screenshots.py — Capture headless screenshots of the Signalpost viewer.
Uses Playwright to capture 1280x800 (desktop) and 390x844 (mobile) screenshots
for the directory, a rich company, a sparse company, and the compare view.
"""
from __future__ import annotations

import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWER_HTML = (ROOT / "out" / "viewer" / "index.html").resolve()
OUTPUT_DIR = (ROOT / "reports" / "ux").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def capture():
    file_url = VIEWER_HTML.as_uri()
    print(f"Loading viewer from {file_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        # 1. Desktop Viewport (1280x800)
        desktop_page = browser.new_page(viewport={"width": 1280, "height": 800})
        desktop_page.goto(file_url, wait_until="networkidle")
        desktop_page.wait_for_timeout(500)

        # Directory / Default Desktop
        desktop_page.screenshot(path=str(OUTPUT_DIR / "directory-desktop.png"), full_page=False)
        print("Captured directory-desktop.png")

        # Rich Company (912569608)
        desktop_page.goto(f"{file_url}#912569608", wait_until="networkidle")
        desktop_page.wait_for_timeout(500)
        desktop_page.screenshot(path=str(OUTPUT_DIR / "rich-company-desktop.png"), full_page=False)
        print("Captured rich-company-desktop.png")

        # Sparse Company (835606252)
        desktop_page.goto(f"{file_url}#835606252", wait_until="networkidle")
        desktop_page.wait_for_timeout(500)
        desktop_page.screenshot(path=str(OUTPUT_DIR / "sparse-company-desktop.png"), full_page=False)
        print("Captured sparse-company-desktop.png")

        # Compare View
        # Add two companies to compare
        desktop_page.click("#toggle-compare-btn")
        desktop_page.wait_for_timeout(200)
        desktop_page.goto(f"{file_url}#912569608", wait_until="networkidle")
        desktop_page.wait_for_timeout(300)
        desktop_page.click("#toggle-compare-btn")
        desktop_page.wait_for_timeout(200)
        desktop_page.click("#compare-btn")
        desktop_page.wait_for_timeout(400)
        desktop_page.screenshot(path=str(OUTPUT_DIR / "compare-desktop.png"), full_page=False)
        print("Captured compare-desktop.png")

        desktop_page.close()

        # 2. Mobile Viewport (390x844)
        mobile_page = browser.new_page(viewport={"width": 390, "height": 844})
        mobile_page.goto(file_url, wait_until="networkidle")
        mobile_page.wait_for_timeout(500)

        # Directory Mobile
        mobile_page.screenshot(path=str(OUTPUT_DIR / "directory-mobile.png"), full_page=False)
        print("Captured directory-mobile.png")

        # Rich Company Mobile
        mobile_page.goto(f"{file_url}#912569608", wait_until="networkidle")
        mobile_page.wait_for_timeout(500)
        mobile_page.screenshot(path=str(OUTPUT_DIR / "rich-company-mobile.png"), full_page=False)
        print("Captured rich-company-mobile.png")

        # Sparse Company Mobile
        mobile_page.goto(f"{file_url}#835606252", wait_until="networkidle")
        mobile_page.wait_for_timeout(500)
        mobile_page.screenshot(path=str(OUTPUT_DIR / "sparse-company-mobile.png"), full_page=False)
        print("Captured sparse-company-mobile.png")

        # Compare Mobile
        mobile_page.click("#toggle-compare-btn")
        mobile_page.wait_for_timeout(200)
        mobile_page.goto(f"{file_url}#962583024", wait_until="networkidle")
        mobile_page.wait_for_timeout(300)
        mobile_page.click("#toggle-compare-btn")
        mobile_page.wait_for_timeout(200)
        mobile_page.click("#compare-btn")
        mobile_page.wait_for_timeout(400)
        mobile_page.screenshot(path=str(OUTPUT_DIR / "compare-mobile.png"), full_page=False)
        print("Captured compare-mobile.png")

        mobile_page.close()
        browser.close()

    print(f"All 8 screenshots successfully generated under {OUTPUT_DIR}")


if __name__ == "__main__":
    capture()
