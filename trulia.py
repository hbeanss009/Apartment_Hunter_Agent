import asyncio
import random
from playwright.async_api import async_playwright
import pandas as pd


async def stealth_async(page):
    """
    Minimal 'stealth' shim to reduce obvious automation signals.
    This avoids relying on playwright_stealth, which may change APIs.
    """
    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """
    )


async def scrape_trulia_94103(headless=False):
    async with async_playwright() as p:
        # 1. Launch browser: try Chromium first, then system Chrome if needed
        try:
            browser = await p.chromium.launch(headless=headless)
        except Exception as e:
            print(f"Chromium not found ({e}). Trying system Chrome...")
            try:
                browser = await p.chromium.launch(headless=headless, channel="chrome")
            except Exception as e2:
                print(f"Chrome not found ({e2}). Running headless with Chromium...")
                browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Enable Stealth
        await stealth_async(page)

        # 2. Targeted URL for SF 94103
        search_url = "https://www.trulia.com/for_rent/37.75291,37.7983,-122.43804,-122.38748_xy/"
        print(f"Opening Trulia for 94103: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

        # Wait for JS to render listings (Trulia loads them dynamically)
        await asyncio.sleep(5)
        # Optional: wait for network to settle so listing API responses finish
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # 3. 'Slow Down' Step: Mimic human reading/loading time
        await asyncio.sleep(random.uniform(2, 4))

        # 4. Human-like incremental scrolling to trigger lazy load
        for _ in range(4):
            scroll_amt = random.randint(400, 800)
            await page.evaluate(f"window.scrollBy(0, {scroll_amt})")
            await asyncio.sleep(random.uniform(1.5, 3))

        # Debug: see what we're actually getting
        title = await page.title()
        print(f"Page title: {title}")
        cards = await page.query_selector_all("[data-testid='property-card-details']")
        if not cards:
            # Try alternate selectors Trulia might use
            cards = await page.query_selector_all("[data-testid='listing-card']")
        if not cards:
            cards = await page.query_selector_all("a[data-testid='property-card-link']")
        if not cards:
            cards = await page.query_selector_all("div[class*='PropertyCard'], div[class*='SearchResult'], li[class*='result']")
        if not cards:
            # Fallback: any link that looks like a listing (e.g. /p/ or /rent/)
            cards = await page.query_selector_all("a[href*='/p/']")
        print(f"Found {len(cards)} property cards on first page.")

        listings = []
        seen_urls = set()
        page_index = 1
        max_listings = 300
        prev_count = 0

        while True:
            print(f"Scraping Trulia page {page_index}... current listings: {len(listings)}")

            # Scroll further on each iteration to trigger lazy-loaded listings
            for _ in range(5):
                scroll_amt = random.randint(600, 1000)
                await page.evaluate(f"window.scrollBy(0, {scroll_amt})")
                await asyncio.sleep(random.uniform(1.5, 3))

            cards = await page.query_selector_all("[data-testid='property-card-details']")
            if not cards:
                cards = await page.query_selector_all("[data-testid='listing-card']")
            if not cards:
                cards = await page.query_selector_all("a[data-testid='property-card-link']")
            if not cards:
                cards = await page.query_selector_all("div[class*='PropertyCard'], div[class*='SearchResult'], li[class*='result']")
            if not cards:
                cards = await page.query_selector_all("a[href*='/p/']")

            for card in cards:
                try:
                    await asyncio.sleep(random.uniform(0.2, 0.4))

                    # Try data-testid selectors first (Trulia's main structure)
                    price_elem = await card.query_selector("[data-testid='property-price']")
                    if not price_elem:
                        price_elem = await card.query_selector(".price, [class*='Price']")
                    price = (await price_elem.inner_text()).strip() if price_elem else "N/A"

                    address_elem = await card.query_selector("[data-testid='property-address']")
                    if not address_elem:
                        address_elem = await card.query_selector("a[href*='/p/']")
                    address = (await address_elem.inner_text()).strip() if address_elem else "N/A"

                    sqft_elem = await card.query_selector("[data-testid='property-floor-space']")
                    if not sqft_elem:
                        sqft_elem = await card.query_selector("[class*='sqft'], [class*='Sqft']")
                    sqft = (await sqft_elem.inner_text()).strip() if sqft_elem else "N/A"

                    beds_elem = await card.query_selector("[data-testid='property-beds']")
                    if not beds_elem:
                        beds_elem = await card.query_selector("[class*='bed'], [class*='Beds']")
                    beds = (await beds_elem.inner_text()).strip() if beds_elem else "Studio"

                    baths_elem = await card.query_selector("[data-testid='property-baths']")
                    if not baths_elem:
                        baths_elem = await card.query_selector("[class*='bath']")
                    baths = (await baths_elem.inner_text()).strip() if baths_elem else "N/A"

                    # Try to capture the listing URL for optional detail-page scraping
                    detail_url = None
                    try:
                        link_elem = await card.query_selector("a[href*='/p/']")
                        if link_elem:
                            href = await link_elem.get_attribute("href")
                            if href:
                                detail_url = href if href.startswith("http") else f"https://www.trulia.com{href}"
                    except Exception:
                        detail_url = None

                    # Skip duplicates based on detail URL
                    if detail_url and detail_url in seen_urls:
                        continue
                    if detail_url:
                        seen_urls.add(detail_url)

                    img_elem = await card.query_selector("img")
                    photo_url = (await img_elem.get_attribute("src")) if img_elem else "No Image"
                    if not photo_url:
                        photo_url = "No Image"

                    amenities = []
                    amenity_tags = await card.query_selector_all("[data-testid='property-amenity']")
                    if not amenity_tags:
                        amenity_tags = await card.query_selector_all("[class*='amenity'], [class*='highlight']")
                    for tag in amenity_tags:
                        amenities.append(await tag.inner_text())

                    # If we did not find amenities on the search card, try the detail page
                    if not amenities and detail_url:
                        try:
                            detail_page = await context.new_page()
                            await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                            await asyncio.sleep(random.uniform(1.5, 3))
                            detail_amenity_tags = await detail_page.query_selector_all(
                                "[data-testid='amenity-item'], [data-testid='amenity-badge'], li[class*='amenity']"
                            )
                            for tag in detail_amenity_tags:
                                text = (await tag.inner_text()).strip()
                                if text:
                                    amenities.append(text)
                            await detail_page.close()
                        except Exception:
                            try:
                                await detail_page.close()
                            except Exception:
                                pass

                    # Only add if we got at least price or address (avoid empty rows)
                    if price != "N/A" or address != "N/A":
                        listings.append({
                            "Zip_Code": "94103",
                            "Price": price,
                            "Beds": beds,
                            "Baths": baths,
                            "Sqft": sqft,
                            "Amenities": ", ".join(amenities),
                            "Photo_URL": photo_url or "No Image",
                            "Address": address,
                            "Detail_URL": detail_url or ""
                        })
                except Exception:
                    continue

            current_count = len(listings)
            if current_count >= max_listings:
                print(f"Reached max listings limit ({max_listings}).")
                break
            if current_count == prev_count:
                print("No new listings found after scrolling; stopping.")
                break
            prev_count = current_count
            page_index += 1

        if cards and not listings:
            print("Debug: cards found but no data extracted. First card HTML (snippet):")
            try:
                html = await cards[0].evaluate("el => el.outerHTML")
                print(html[:500] if len(html) > 500 else html)
            except Exception:
                pass

        await browser.close()
        return pd.DataFrame(listings)

if __name__ == "__main__":
    df = asyncio.run(scrape_trulia_94103())
    print(f"\nScraped {len(df)} listings. First few rows:")
    print(df.head())
    df.to_csv("trulia.csv", index=False)