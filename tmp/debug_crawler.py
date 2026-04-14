import asyncio
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.services.browser import BrowserSession
from src.services.website_crawler import WebsiteEmailCrawler
from src.core.models import AppSettings

async def test_crawler():
    settings = AppSettings()
    # Ensure our discovery keywords are there
    print(f"Discovery paths: {settings.email_discovery_paths}")
    
    session = BrowserSession(settings)
    await session.start()
    
    crawler = WebsiteEmailCrawler(session)
    # Target website
    url = "https://drk-sok.de"
    print(f"Testing crawler for: {url}")
    
    email, source, socials = await crawler.find_email(url, job_id="TEST-DEBUG")
    
    print(f"\n--- RESULTS ---")
    print(f"Email: {email}")
    print(f"Source: {source}")
    print(f"Socials: {socials}")
    
    await session.stop()

if __name__ == "__main__":
    asyncio.run(test_crawler())
