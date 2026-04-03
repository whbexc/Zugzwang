import asyncio
import sys
from src.core.models import SearchConfig
from src.services.browser import BrowserSession
from src.services.ausbildung_scraper import AusbildungScraper

import logging

logging.basicConfig(level=logging.DEBUG)

async def test_scraper():
    from src.core.config import config_manager
    session = BrowserSession(config_manager.settings)
    session.settings.default_headless = False
    await session.start()
    
    config = SearchConfig(
        job_title="Pflegefachmann",
        city="",
        max_results=5,
        offer_type="Ausbildung/Duales Studium"
    )
    
    scraper = AusbildungScraper(session, config, "test-job-ausbildung")
    
    async for record in scraper.scrape():
        print(f"SCRAPED: {record.company_name} | {record.email} | {record.address}")
        
    await session.stop()

if __name__ == "__main__":
    asyncio.run(test_scraper())
