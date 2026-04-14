import asyncio
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.services.browser import BrowserSession
from src.core.models import AppSettings

async def main():
    settings = AppSettings()
    session = BrowserSession(settings)
    await session.start()
    
    urls = [
        "https://ukaachen.de",
        "https://ukaachen.de/impressum",
        "https://www.ukaachen.de",
        "https://www.ukaachen.de/impressum"
    ]
    
    from src.services.email_extractor import extract_emails_from_html
    
    for url in urls:
        print(f"Fetching {url}...")
        html = await session.fetch_url_content_fast(url)
        if html:
            print(f"  SUCCESS: {len(html)} bytes")
            if "impressum" in url and "www" in url:
                with open("tmp/ukaachen_impressum.html", "w", encoding="utf-8") as f:
                    f.write(html)
            
            emails = extract_emails_from_html(html)
            print(f"  Emails found: {emails}")
        else:
            print(f"  FAILED")
            
    from src.services.email_extractor import extract_emails_from_text
    print("\nManual Deobfuscation Test:")
    test_strings = [
        "info (at) ukaachen.de",
        "jobs [at] company [dot] de",
        "hr{at}firm.de",
        "personal (ät) klinik . de",
        "contact at domain dot com"
    ]
    for ts in test_strings:
        print(f"  '{ts}' -> {extract_emails_from_text(ts)}")

    await session.stop()

if __name__ == "__main__":
    asyncio.run(main())
