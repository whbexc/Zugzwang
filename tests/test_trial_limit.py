import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.ausbildung_scraper import AusbildungScraper
from src.services.aubiplus_scraper import AubiPlusScraper
from src.core.models import SearchConfig, SourceType

def run_async(coro):
    return asyncio.run(coro)

def test_ausbildung_scraper_enforces_trial_limit():
    async def _test():
        # Mock dependencies
        session = MagicMock()
        session.new_page = AsyncMock()
        session.navigate = AsyncMock(return_value=True)
        
        config = SearchConfig(job_title="Test", city="Berlin", max_results=5)
        scraper = AusbildungScraper(session, config, "job-123")
        
        # Mock LicenseManager to hit limit immediately
        with patch("src.services.ausbildung_scraper.LicenseManager") as mock_lm, \
             patch("src.services.ausbildung_scraper.event_bus") as mock_bus, \
             patch.object(scraper, "_extract_job_detail", AsyncMock(return_value=MagicMock(company_name="TestCorp"))):
            
            mock_lm.can_extract.return_value = False
            
            # Mock the card harvesting
            with patch.object(session.new_page.return_value, "query_selector_all", AsyncMock(return_value=[MagicMock()])):
                session.new_page.return_value.query_selector_all.return_value[0].get_attribute = AsyncMock(return_value="/job/1")
                
                # Run scraper
                results = []
                async for record in scraper.scrape():
                    results.append(record)
                
                # Verify it stopped and emitted events
                assert len(results) == 0
                mock_lm.can_extract.assert_called_once()
                mock_bus.emit.assert_any_call(mock_bus.TRIAL_LIMIT_REACHED, job_id="job-123")
    
    run_async(_test())

def test_aubiplus_scraper_enforces_trial_limit():
    async def _test():
        # Mock dependencies
        session = MagicMock()
        session.new_page = AsyncMock()
        session.navigate = AsyncMock(return_value=True)
        
        config = SearchConfig(job_title="Test", city="Berlin", max_results=5)
        scraper = AubiPlusScraper(session, config, "job-123")
        
        # Mock LicenseManager to hit limit immediately
        with patch("src.services.aubiplus_scraper.LicenseManager") as mock_lm, \
             patch("src.services.aubiplus_scraper.event_bus") as mock_bus, \
             patch.object(scraper, "_extract_job_detail", AsyncMock(return_value=MagicMock(company_name="TestCorp"))):
            
            mock_lm.can_extract.return_value = False
            
            # Mock the card harvesting
            with patch.object(session.new_page.return_value, "query_selector_all", AsyncMock(return_value=[MagicMock()])):
                session.new_page.return_value.query_selector_all.return_value[0].query_selector = AsyncMock(return_value=MagicMock())
                session.new_page.return_value.query_selector_all.return_value[0].query_selector.return_value.get_attribute = AsyncMock(return_value="/job/1")
                
                # Run scraper
                results = []
                async for record in scraper.scrape():
                    results.append(record)
                
                # Verify it stopped and emitted events
                assert len(results) == 0
                mock_lm.can_extract.assert_called_once()
                mock_bus.emit.assert_any_call(mock_bus.TRIAL_LIMIT_REACHED, job_id="job-123")
    
    run_async(_test())
