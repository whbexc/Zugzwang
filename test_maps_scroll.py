import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto('https://www.google.com/maps')
        
        # Dismiss consent
        try:
            await page.locator('//button[contains(., "Accept all")]').first.click(timeout=3000)
            await page.wait_for_timeout(1000)
        except: pass
        try:
            await page.locator('//button[contains(., "Alle akzeptieren")]').first.click(timeout=3000)
            await page.wait_for_timeout(1000)
        except: pass
        
        print('Typing search...')
        search = page.locator('//input[@id="searchboxinput"] | //input[@role="combobox"]').first
        # Using a highly populated query
        await search.fill('Restaurants in Hamburg')
        await page.keyboard.press('Enter')
        
        print('Waiting for listings...')
        await page.wait_for_selector('//a[contains(@href, "maps/place") or contains(@class, "hfpxzc")]', timeout=10000)
        await page.wait_for_timeout(2000)
        
        sidebar_sel = 'div[role="feed"], div.m6QErb.DxyBCb.kA9KIf.dS8AEf'
        sidebar = page.locator(sidebar_sel).first
        
        count1 = await page.locator('//a[contains(@href, "maps/place") or contains(@class, "hfpxzc")]').count()
        print(f'Initial Count: {count1}')

        print('Attempting evaluate scroll...')
        await sidebar.evaluate('''
            async (el) => {
                let scrollable = el;
                // find closest overflow container
                while (scrollable && window.getComputedStyle(scrollable).overflowY !== "auto" && window.getComputedStyle(scrollable).overflowY !== "scroll") {
                    scrollable = scrollable.parentElement;
                }
                let target = scrollable || el;
                console.log("Evaluating scroll on:", target.className, "with overflow:", window.getComputedStyle(target).overflowY);
                for (let i = 0; i < 10; i++) {
                    target.scrollBy(0, 800);
                    await new Promise(r => setTimeout(r, 150));
                }
            }
        ''')
        await page.wait_for_timeout(2000)
        count2 = await page.locator('//a[contains(@href, "maps/place") or contains(@class, "hfpxzc")]').count()
        print(f'Count after JS eval: {count2}')

        print('Attempting Wheel scroll...')
        await sidebar.hover()
        for _ in range(10):
            await page.mouse.wheel(0, 800)
            await page.wait_for_timeout(150)
            
        await page.wait_for_timeout(2000)
        count3 = await page.locator('//a[contains(@href, "maps/place") or contains(@class, "hfpxzc")]').count()
        print(f'Count after Wheel: {count3}')
        
        await browser.close()

asyncio.run(main())
