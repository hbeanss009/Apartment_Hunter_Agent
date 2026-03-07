"""
recommend.py is an agent that:

- Takes the text output from Analyse.py (matching apartments) plus the user's
  preferences (including nice-to-have amenities).
- Scores and ranks those apartments, recommending the best ones to the user.
- Interacts with the user:
  * If the user updates NICE-TO-HAVE amenities, it re-scores the same list.
  * If the user updates MUST-HAVE amenities, it calls Analyse.get_matching_apartments
    again with the updated preferences, then re-scores the new list.
"""

import os
from typing import List

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from Analyse import get_matching_apartments

load_dotenv()


def recommend_apartments(analyse_output: str, user_preferences: List[str]) -> str:
    """
    Take the raw text output from Analyse.py (matching apartments) and the
    user_preferences list, and ask Gemini to rank and recommend the best
    apartments based primarily on nice-to-have amenities.

    user_preferences is:
      [neighbourhoods, min_bedrooms, min_bathrooms,
       budget_range, must_have_amenities, nice_to_have_amenities]
    """
    if not analyse_output or not analyse_output.strip():
        return "No matching apartments were found to recommend."

    neighbourhoods, min_bedrooms, min_bathrooms, budget_range, must_have, nice_to_have = (
        user_preferences + [""] * 6
    )[:6]

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
                """You are an apartment rental recommendation agent.

You receive:
- A list of apartments that already match the user's MUST-HAVE criteria (from Analyse.py).
- The user's preferences (neighbourhoods, min_bedrooms, min_bathrooms, budget_range,
  must_have_amenities, nice_to_have_amenities).

Your tasks:
1. Analyse each listing and assign a score based primarily on nice_to_have_amenities.
   - Higher score if more nice-to-have amenities are present.
   - Never hallucinate amenities; if unknown, say 'Amenities: unknown'.
2. Break ties using:
   - Closeness to the user's budget midpoint,
   - Better neighbourhood match,
   - Higher beds/baths when still within budget.
3. Rank the listings from best to weakest match.
4. Return the TOP 10 listings in order of score.
   For EACH listing, include at least:
   - Title or address
   - Source (Craigslist/Trulia if you can infer it)
   - Price
   - Explicit bed count
   - Explicit bath count
   - Full amenities list (or 'unknown' if missing)
   - Listing URL
   - At least one photo URL if available in the input text
   - A one-sentence explanation of why you recommended it.
5. At the end, briefly summarise how you scored and ranked them.
""",
            ),
            (
                "human",
                "User criteria:\n{user_criteria}\n\nMatching apartments from Analyse.py:\n\n{analyse_output}",
            ),
        ]
    )

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not set. Add it to your .env file for the recommendation agent to work."
        )

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
    chain = prompt | llm

    raw_response = chain.invoke(
        {"user_criteria": user_criteria, "analyse_output": analyse_output}
    )

    return raw_response.content if hasattr(raw_response, "content") else str(raw_response)


def _ask_yes_no(prompt_text: str) -> bool:
    """Simple yes/no helper."""
    while True:
        ans = input(prompt_text).strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please answer 'yes' or 'no'.")


def main() -> None:
    """
    Interactive entrypoint:
    - Prompts the user for preferences (or could be wired to use main.USER_PREFERENCES).
    - Calls Analyse.get_matching_apartments once for MUST-HAVE filtering.
    - Calls recommend_apartments to rank and explain based on NICE-TO-HAVE.
    - Lets the user adjust must-have or nice-to-have amenities and re-run.
    """
    print("Welcome to the recommendation agent.\n")

    # Defaults: Mission/Hayes, 2 bed, 1 bath, $2000–4000, washer/dryer + dishwasher
    default_neighbourhoods = "Mission, Hayes"
    default_min_bedrooms = "2"
    default_min_bathrooms = "1"
    default_budget = "2000-4000"
    default_must_have = "washer dryer, dishwasher"
    default_nice_to_have = ""

    def _prompt(prompt: str, default: str) -> str:
        if default:
            s = input(f"{prompt} [{default}]: ").strip()
            return s if s else default
        return input(f"{prompt}: ").strip()

    neighbourhoods = _prompt("Enter the list of neighbourhoods you are interested in", default_neighbourhoods)
    min_bedrooms = _prompt("Enter the minimum number of bedrooms you are looking for", default_min_bedrooms)
    min_bathrooms = _prompt("Enter the minimum number of bathrooms you are looking for", default_min_bathrooms)
    budget_range = _prompt("Enter your budget range for the apartments", default_budget)
    must_have_amenities = _prompt(
        "Enter any amenities/facilities that you think are must have in your apartment",
        default_must_have,
    )
    nice_to_have_amenities = _prompt(
        "Enter any amenities/facilities that are nice to have for your apartment",
        default_nice_to_have,
    )

    prefs = [
        neighbourhoods,
        min_bedrooms,
        min_bathrooms,
        budget_range,
        must_have_amenities,
        nice_to_have_amenities,
    ]

    while True:
        print("\nRunning Analyse agent with current MUST-HAVE criteria...\n")
        matches = get_matching_apartments(prefs)

        print("\nRanking apartments based on NICE-TO-HAVE amenities...\n")
        recommendations = recommend_apartments(matches, prefs)
        print("\nRecommended apartments:\n")
        print(recommendations)

        if _ask_yes_no("\nAre you happy with these recommendations? (yes/no): "):
            print("Thank you for using the recommendation agent.")
            break

        print(
            "\nWould you like to change your must-have amenities, nice-to-have amenities, or both?"
        )
        choice = input("Type 'must', 'nice', 'both', or 'quit': ").strip().lower()

        if choice == "quit":
            print("Exiting without further changes.")
            break
        if choice in ("must", "both"):
            must_have_amenities = input(
                "Enter your UPDATED must-have amenities (comma-separated): "
            )
            prefs[4] = must_have_amenities
        if choice in ("nice", "both"):
            nice_to_have_amenities = input(
                "Enter your UPDATED nice-to-have amenities (comma-separated): "
            )
            prefs[5] = nice_to_have_amenities


if __name__ == "__main__":
    main()
