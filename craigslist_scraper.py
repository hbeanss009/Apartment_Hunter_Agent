from __future__ import annotations

from dataclasses import dataclass, asdict
from random import randint
from time import sleep
from typing import Any, Iterable, List

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) "
    "Gecko/20100101 Firefox/117.0"
)


@dataclass
class Listing:
    url: str
    title: str | None
    price: int | None
    bedrooms: int | None
    bathrooms: float | None
    neighbourhood: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_price(text: str | None) -> int | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def _parse_housing_info(text: str | None) -> tuple[int | None, float | None]:
    """
    Example housing text: '2br - 850ft2 - (Downtown)'
    We only care about the '2br' and maybe '1ba' if present.
    """
    if not text:
        return None, None
    bedrooms = None
    bathrooms = None

    parts = text.lower().replace("\n", " ").split()
    for part in parts:
        if part.endswith("br"):
            num = "".join(ch for ch in part if ch.isdigit())
            if num:
                bedrooms = int(num)
        elif part.endswith("ba"):
            num = "".join(ch for ch in part if (ch.isdigit() or ch == "."))
            if num:
                try:
                    bathrooms = float(num)
                except ValueError:
                    pass

    return bedrooms, bathrooms


def _get_page_soup(url: str) -> BeautifulSoup | None:
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException:
        return None


def _get_listing_urls_for_city(city: str, max_pages: int = 3) -> List[str]:
    """
    Collect listing URLs for a given Craigslist city.

    We mirror the Medium article pattern but:
    - Limit to a small number of pages (max_pages) to avoid huge scrapes.
    - Target apartments/housing for rent (`apa`) instead of cars.
    """
    urls: List[str] = []
    base = f"https://{city}.craigslist.org/search/apa"

    for page in range(max_pages):
        offset = page * 120
        page_url = f"{base}?s={offset}&hasPic=1"
        soup = _get_page_soup(page_url)
        if not soup:
            break

        # Craigslist markup can change; this selector follows the reference article
        # pattern (anchors that wrap the listing image/title).
        anchors = soup.find_all("a", class_="result-image gallery")
        if not anchors:
            # Fallback: more generic search-result link
            anchors = soup.select("a.result-title, a.result-title.hdrlnk")

        if not anchors:
            break

        for a in anchors:
            href = a.get("href")
            if href and href.startswith("http"):
                urls.append(href)

        # Be polite: sleep a short, random interval
        sleep(randint(1, 3))

    return urls


def _scrape_listing(url: str) -> Listing | None:
    soup = _get_page_soup(url)
    if not soup:
        return None

    # Title
    title_el = soup.find("span", id="titletextonly")
    title = title_el.get_text(strip=True) if title_el else None

    # Price
    price_el = soup.find("span", class_="price")
    price = _parse_price(price_el.get_text(strip=True) if price_el else None)

    # Housing info (bedrooms, bathrooms, etc.)
    housing_el = soup.find("span", class_="housing")
    bedrooms, bathrooms = _parse_housing_info(
        housing_el.get_text(strip=True) if housing_el else None
    )

    # Neighbourhood (if present)
    hood_el = soup.find("span", class_="postingtitletext")
    neighbourhood = None
    if hood_el:
        hood_span = hood_el.find("small")
        if hood_span:
            neighbourhood = hood_span.get_text(strip=True).strip("()")

    return Listing(
        url=url,
        title=title,
        price=price,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        neighbourhood=neighbourhood,
    )


def scrape_craigslist(
    city: str,
    neighbourhoods: Iterable[str],
    min_bedrooms: int,
    min_bathrooms: int,
    max_budget: int,
    must_have_amenities: Iterable[str] | None = None,
    nice_to_have_amenities: Iterable[str] | None = None,
) -> List[dict[str, Any]]:
    """
    High-level helper that:
    - Collects listing URLs for the given city.
    - Scrapes each listing for basic attributes.
    - Applies simple filters based on bedrooms / price.

    Right now, amenities and neighbourhoods are *not* deeply parsed from
    the description; you can extend this function later to do that.
    """
    must_have_amenities = [a.strip().lower() for a in (must_have_amenities or []) if a]
    nice_to_have_amenities = [
        a.strip().lower() for a in (nice_to_have_amenities or []) if a
    ]
    target_neighbourhoods = {n.strip().lower() for n in neighbourhoods if n}

    listing_urls = _get_listing_urls_for_city(city)
    results: List[dict[str, Any]] = []

    for url in listing_urls:
        listing = _scrape_listing(url)
        if not listing:
            continue

        # Basic numeric filters
        if listing.bedrooms is not None and listing.bedrooms < min_bedrooms:
            continue
        if listing.bathrooms is not None and listing.bathrooms < min_bathrooms:
            continue
        if listing.price is not None and listing.price > max_budget:
            continue

        # Simple neighbourhood filter (if user provided any)
        if target_neighbourhoods and listing.neighbourhood:
            if listing.neighbourhood.lower() not in target_neighbourhoods:
                continue

        # NOTE: Amenity filtering would require scraping the description text.
        # You can extend `_scrape_listing` to capture that and then check for
        # presence of each amenity string here.

        results.append(listing.to_dict())

        # Be polite to Craigslist
        sleep(randint(1, 3))

    return results

