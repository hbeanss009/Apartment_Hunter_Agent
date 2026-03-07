import os
import requests
import pandas as pd
from dotenv import load_dotenv

APIFY_TOKEN_ENV_VAR = "APIFY_API_TOKEN"
ACTOR_ID = "maxcopell~zillow-scraper" 

def fetch_zillow_data(max_items: int = 50) -> pd.DataFrame:
    load_dotenv()

    token = os.getenv(APIFY_TOKEN_ENV_VAR)
    if not token:
        raise RuntimeError(f"Missing Apify API token in .env file.")

    # Using the sync endpoint to get results immediately.
    # NOTE: maxItems must be passed as a QUERY PARAM for this endpoint,
    # not inside the actor input JSON.
    url = (
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
        f"?token={token}&maxItems={max_items}"
    )

    # Actor input JSON (matches the official input schema).
    payload = {
        "searchUrls": [
            {
                "url": "https://www.zillow.com/homes/for_sale/?searchQueryState=%7B%22isMapVisible%22%3Atrue%2C%22mapBounds%22%3A%7B%22west%22%3A-124.61572460426518%2C%22east%22%3A-120.37225536598393%2C%22south%22%3A36.71199595991113%2C%22north%22%3A38.74934086729303%7D%2C%22filterState%22%3A%7B%22sort%22%3A%7B%22value%22%3A%22days%22%7D%2C%22ah%22%3A%7B%22value%22%3Atrue%7D%7D%2C%22isListVisible%22%3Atrue%2C%22customRegionId%22%3A%227d43965436X1-CRmxlqyi837u11_1fi65c%22%7D"
            }
        ]
    }

    print(f"Starting Apify Actor {ACTOR_ID}...")
    resp = requests.post(url, json=payload, timeout=600)
    
    if resp.status_code != 201 and resp.status_code != 200:
        print(f"Error: {resp.text}")
        resp.raise_for_status()

    data = resp.json()
    return pd.DataFrame(data)

if __name__ == "__main__":
    try:
        # Use a very small max_items to fit within current Apify credits.
        df = fetch_zillow_data(max_items=1) 
        
        if not df.empty:
            print(f"\nSuccess! Scraped {len(df)} listings.")
            print(df[['address', 'price', 'url']].head()) # Showing key columns
            df.to_csv("zillow_results.csv", index=False)
            print("\nFile saved to zillow_results.csv")
        else:
            print("No data returned.")
            
    except Exception as e:
        print(f"An error occurred: {e}")