import requests
import pandas as pd
import time
import re
import json
from bs4 import BeautifulSoup
from typing import Dict, Optional

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_post_details(post_url: str, default_neighborhood: Optional[str] = None) -> Dict:
    """Visits the individual listing and extracts all details using a multi-source search."""
    try:
        resp = requests.get(post_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {}
        
        inner_soup = BeautifulSoup(resp.content, "html.parser")
        
        # --- 1. CAPTURE ALL SOURCE TEXT ---
        # Craigslist has changed: many pages no longer have postingtitle/attrgroup; data is in body.
        title_el = inner_soup.find("h2", class_="postingtitle") or inner_soup.find("span", id="titletextonly")
        title_text = title_el.get_text(strip=True) if title_el else ""
        attr_ps = inner_soup.find_all("p", class_="attrgroup")
        attr_text = " ".join([p.get_text(separator=" ", strip=True) for p in attr_ps])
        body_el = inner_soup.find("section", id="postingbody")
        body_text = body_el.get_text(separator=" ", strip=True) if body_el else ""
        full_blob = f"{title_text} {attr_text} {body_text}"
        full_blob_lower = full_blob.lower()

        # --- 2. EXTRACTION (body-first: many listings use "Beds: 1 Baths: 1 Square Feet: 732") ---
        # Price: try sidebar span.price first (many listings put it only there), then title/blob
        price_val = "N/A"
        price_span = inner_soup.find("span", class_="price")
        if price_span:
            pt = price_span.get_text(strip=True)
            if re.match(r'\$[\d,]+', pt):
                price_val = pt
        if price_val == "N/A":
            price_match = re.search(r'\$[\d,]+', title_text) or re.search(r'\$[\d,]+', full_blob)
            price_val = price_match.group(0) if price_match else "N/A"
        # Beds: explicit "Beds: N" or "N bed / bedroom"
        beds_match = (
            re.search(r'Beds?:\s*(\d+)', full_blob, re.I)
            or re.search(r'(\d+)\s*(?:br|bedroom|bed|beds)\b', full_blob_lower)
        )
        # Baths: explicit "Baths: N" or "N ba / bath / bathroom"
        baths_match = (
            re.search(r'Baths?:\s*([\d.]+)', full_blob, re.I)
            or re.search(r'([\d.]+)\s*(?:ba|bath|baths|bathroom|bathrooms)\b', full_blob_lower)
        )
        # Sqft: "Square Feet: N" or "N square feet" or "N sqft / ft"
        sqft_match = (
            re.search(r'Square\s*Feet:\s*(\d+)', full_blob, re.I)
            or re.search(r'(\d+)\s*(?:square\s*feet|sq\.?\s*ft|ft2|\s*ft\b)', full_blob_lower)
        )

        # Initial numeric values from regex
        beds_val = beds_match.group(1) if beds_match else None
        baths_val = baths_match.group(1) if baths_match else None
        sqft_val = sqft_match.group(1) if sqft_match else None

        # Additional combined pattern: "2br/1.5ba" or "2br | 1.5ba"
        combo = re.search(r'(\d+)\s*br\s*[/|]\s*([\d.]+)\s*ba', full_blob_lower)
        if combo:
            if beds_val is None:
                beds_val = combo.group(1)
            if baths_val is None:
                baths_val = combo.group(2)

        # Heuristic: studio listings
        if beds_val is None and "studio" in full_blob_lower:
            beds_val = "0"

        # JSON-LD fallback (if present)
        if beds_val is None or baths_val is None or sqft_val is None:
            for script in inner_soup.find_all("script", type="application/ld+json"):
                try:
                    raw = script.string or ""
                    if not raw.strip():
                        continue
                    data = json.loads(raw)
                except Exception:
                    continue

                objs = data if isinstance(data, list) else [data]
                for obj in objs:
                    if not isinstance(obj, dict):
                        continue
                    if beds_val is None:
                        v = obj.get("numberOfRooms") or obj.get("numberOfBedrooms")
                        if isinstance(v, (int, float, str)):
                            beds_val = str(v)
                    if baths_val is None:
                        v = obj.get("numberOfBathroomsTotal") or obj.get("numberOfBathrooms")
                        if isinstance(v, (int, float, str)):
                            baths_val = str(v)
                    if sqft_val is None:
                        fs = obj.get("floorSize")
                        if isinstance(fs, dict):
                            v = fs.get("value") or fs.get("Value")
                            if isinstance(v, (int, float, str)):
                                sqft_val = str(v)

                if beds_val is not None and baths_val is not None and sqft_val is not None:
                    break

        # Neighborhood: parentheses in title or common SF neighborhood names
        hood_match = re.search(r'\((.*?)\)', title_text)

        # --- 3. AMENITIES EXTRACTION ---
        # Merge sidebar tags and list items from the description
        amenities_list = []
        
        # Get the 'tags' (e.g., cats are ok, laundry in bldg)
        for span in inner_soup.select("p.attrgroup span"):
            txt = span.get_text(strip=True)
            if not any(x in txt.lower() for x in ["br", "ba", "ft", "available"]):
                amenities_list.append(txt)
        
        # Get bulleted list items from the body (often uses • or -)
        body_amenities = re.findall(r'[•\-]\s*([^\n•\-]+)', body_text)
        amenities_list.extend([a.strip() for a in body_amenities if len(a) < 100])

        neighborhood_val = hood_match.group(1).strip() if hood_match else None
        if not neighborhood_val and default_neighborhood:
            neighborhood_val = default_neighborhood.strip()
        if not neighborhood_val:
            neighborhood_val = "San Francisco"  # final fallback so it is never empty

        return {
            "Price": price_val,
            "Beds": beds_val or "N/A",
            "Baths": baths_val or "N/A",
            "Sqft": sqft_val or "N/A",
            "Neighborhood": neighborhood_val,
            "Amenities": ", ".join(list(set(amenities_list))),  # set() removes duplicates
            "URL": post_url,
        }
    except Exception as e:
        print(f"Error scraping {post_url}: {e}")
        return {}

def run_scraper(search_url: str, max_posts: int = 10):
    response = requests.get(search_url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")
    # Targets the modern Craigslist search result structure
    posts = soup.find_all("li", class_="cl-static-search-result")
    
    results = []
    for post in posts[:max_posts]:
        link = post.find("a")
        if not (link and link.get("href")):
            continue

        href = link.get("href")

        # Neighborhood from search results row if available
        hood_el = (
            post.find("span", class_="result-hood")
            or post.find("div", class_="location")
            or post.find("span", class_="housing__location")
        )
        neighborhood = hood_el.get_text(strip=True) if hood_el else ""

        print(f"Processing: {href}")
        details = get_post_details(href, default_neighborhood=neighborhood)
        if details:
            results.append(details)
        time.sleep(1)  # Be polite to the server
            
    df = pd.DataFrame(results)
    df.to_csv("craigslist_full_details.csv", index=False)
    print("Done! Data saved to craigslist_full_details.csv")
    return df

if __name__ == "__main__":
    # Example URL for San Francisco Apartments
    TARGET_URL = "https://sfbay.craigslist.org/search/sfc/apa"
    run_scraper(TARGET_URL, max_posts=10)