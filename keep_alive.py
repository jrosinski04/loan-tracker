import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        # Launching headless browser
        browser = await p.chromium.launch()
        page = await browser.new_page()

        print("Opening loan tracker...")
        await page.goto("https://loan-tracker.streamlit.app/", wait_until="networkidle")

        # Waiting 10 seconds to ensure the page is fully loaded
        print("Simulating activity...")
        await asyncio.sleep(10)

        # Taking a screenshot for verification
        await page.screenshot(path="screenshot.png")
        print("Success!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())