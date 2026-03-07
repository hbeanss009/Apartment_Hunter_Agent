"""
Analyse.py is an agent that:

1. Takes the output CSV files from craigslist.py and trulia.py
2. Follows all the instructions given to it in the prompt (criteria matching,
   neighborhood, beds/baths, budget, must-have and nice-to-have amenities)
3. Returns a list of apartments that match the user's criteria provided in main.py

Main.py collects the user's criteria (neighbourhoods, min_bedrooms, min_bathrooms,
budget_range, must_have_amenities, nice_to_have_amenities) and can pass them to
this module to get back the matching listings.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Default CSV paths produced by craigslist.py and trulia.py
CRAIGSLIST_CSV = "craigslist_full_details.csv"
TRULIA_CSV = "trulia.csv"


def _load_csv_data(craigslist_path: str = CRAIGSLIST_CSV, trulia_path: str = TRULIA_CSV) -> str:
    """Load both CSVs and return a single string summary for the prompt."""
    project_root = Path(__file__).parent
    parts = []

    for name, path in [("craigslist", craigslist_path), ("trulia", trulia_path)]:
        full_path = project_root / path
        if not full_path.exists():
            parts.append(f"[{name}] CSV not found: {path}\n")
            continue
        try:
            df = pd.read_csv(full_path)
            # Limit rows to avoid token overflow; agent still sees a representative set
            head = df.head(500) if len(df) > 500 else df
            parts.append(f"[{name}] Columns: {list(df.columns)}\n{head.to_string()}\n\n")
        except Exception as e:
            parts.append(f"[{name}] Error reading CSV: {e}\n")

    return "\n".join(parts) if parts else "No CSV data available."


def get_matching_apartments(
    user_preferences: list[str],
    craigslist_path: str = CRAIGSLIST_CSV,
    trulia_path: str = TRULIA_CSV,
) -> str:
    """
    Agent entrypoint: take user criteria from main.py, load craigslist and trulia
    CSVs, follow the prompt instructions, and return the agent's response (raw text)
    listing apartments that match the user's criteria.

    user_preferences should be a list in this order:
      [neighbourhoods, min_bedrooms, min_bathrooms, budget_range,
       must_have_amenities, nice_to_have_amenities]
    """
    csv_data = _load_csv_data(craigslist_path, trulia_path)
    neighbourhoods, min_bedrooms, min_bathrooms, budget_range, must_have, nice_to_have = (
        user_preferences
        if len(user_preferences) >= 6
        else (user_preferences + [""] * 6)[:6]
    )

    user_criteria = (
        f"Neighbourhoods: {neighbourhoods}\n"
        f"Minimum bedrooms: {min_bedrooms}\n"
        f"Minimum bathrooms: {min_bathrooms}\n"
        f"Budget range: {budget_range}\n"
        f"Must-have amenities: {must_have}\n"
        f"Nice-to-have amenities: {nice_to_have}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
        (
            "system",
            """You are an apartment rental agent.
1. Use ONLY the listing data provided below (from craigslist.csv and trulia.csv) to find apartments for the user.
2. Match on: neighbourhoods (or the address field in the csv file), min_bedrooms, min_bathrooms, budget_range. 
3. From that pool, check for must_have_amenities. If amenities are missing or unclear, make a best-effort inference from the title, description, and neighborhood, and clearly label when amenities are inferred or unknown instead of excluding the listing.
4. When a listing has missing or N/A fields (e.g. Price, Beds, Baths), use the title and neighborhood to infer suitability and still include it if it could plausibly match. Prefer including plausible matches with a short explanation over excluding them entirely.
5. Return up to 10 apartments that best match the user's criteria, ordered from best to weakest match. Use a clear format (e.g. numbered or bulleted list with title/address, source (Craigslist/Trulia), price, beds, baths, neighborhood, and URL).""",
        ),
            ("human", "Listing data from CSVs:\n\n{csv_data}\n\nUser criteria:\n{user_criteria}"),
        ]
    )

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not set. Add it to your .env file for the Analyse agent (Gemini) to work."
        )
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
    chain = prompt | llm

    raw_response = chain.invoke({
        "csv_data": csv_data,
        "user_criteria": user_criteria,
    })

    if hasattr(raw_response, "content"):
        return raw_response.content
    return str(raw_response)


if __name__ == "__main__":
    sample_preferences = [
        "SOMA, Mission, Downtown, Tenderloin, Financial District, SoMa, South of Market, marina, alamo square, Tenderloin, Financial District",
        "1",
        "1",
        "$1000 - $7000",
        "parking",
        "",
    ]
    result = get_matching_apartments(sample_preferences)
    print("\nMatching apartments:")
    if not result or not result.strip():
        print("No matching apartments were found for the sample criteria or the model returned an empty response.")
    else:
        print(result)
