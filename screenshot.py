from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:3000')
    time.sleep(2)  # Wait for page to load
    page.screenshot(path='screenshot.png')

    # Fill prompt to enable generate button
    page.fill('textarea[aria-label="Describe what you want compiled"]', 'Test prompt')
    time.sleep(1)

    # Focus generate button to check outline
    page.focus('button:has-text("Generate")')
    time.sleep(1)
    page.screenshot(path='screenshot_generate_focused.png')

    browser.close()
