from discovery import run_discovery
from Analyse import get_matching_apartments


def main() -> None:
    """
    Ask the user for input, store it in parameters, run discovery (scrapers),
    then pass criteria to the Analyse agent to get a list of matching apartments.
    """
    neighbourhoods = input("Enter the list of neighbourhoods you are interested in: ")
    min_bedrooms = input("Enter the minimum number of bedrooms you are looking for: ")
    min_bathrooms = input("Enter the minimum number of bathrooms you are looking for: ")
    budget_range = input("Enter your budget range for the apartments: ")
    must_have_amenities = input("Enter any amenities/facilities that you think are must have: ")
    nice_to_have_amenities = input("Enter any amenities/facilities that are nice to have: ")
    user_preferences = [
        neighbourhoods,
        min_bedrooms,
        min_bathrooms,
        budget_range,
        must_have_amenities,
        nice_to_have_amenities,
    ]

    # Run discovery so craigslist.csv and trulia.csv are up to date
    results = run_discovery()
    print("\nDiscovery completed. Sources and row counts:")
    for source, df in results.items():
        print(f"- {source}: {len(df)} rows")

    # Analyse agent: takes those CSV outputs and returns raw response with matching apartments
    output = get_matching_apartments(user_preferences)
    print("\nApartments matching your criteria:")
    if not output or not output.strip():
        print("No matching apartments were found for your criteria or the model returned an empty response.")
    else:
        print(output)

if __name__ == "__main__":
    main()

