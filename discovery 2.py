# This file coordinates discovery and aggregates results from all scrapers.
from typing import Dict
from pathlib import Path
import subprocess
import pandas as pd


def run_discovery() -> Dict[str, pd.DataFrame]:
    """
    Run all scrapers (Craigslist, Trulia, Zillow) and return their CSV outputs
    as pandas DataFrames.

    - craigslist.py is expected to write 'craigslist.csv'
    - trulia.py is expected to write 'trulia.csv'
    - zillow.py is expected to write 'zillow_results.csv'
    """
    project_root = Path(__file__).parent

    def _run_script(script_name: str) -> None:
        """Run a scraper script as a subprocess, logging any errors."""
        result = subprocess.run(
            ["python3", script_name],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[{script_name}] exited with code {result.returncode}")
            if result.stderr:
                print(result.stderr)

    # Run each scraper; they handle their own CSV writing.
    _run_script("craigslist.py")
    _run_script("trulia.py")
    _run_script("zillow.py")

    # Load CSVs back into DataFrames (empty DataFrame if a CSV is missing).
    outputs: Dict[str, pd.DataFrame] = {}
    mapping = {
        "craigslist": "craigslist.csv",
        "trulia": "trulia.csv",
        "zillow": "zillow_results.csv",
    }

    for key, filename in mapping.items():
        csv_path = project_root / filename
        if csv_path.exists():
            outputs[key] = pd.read_csv(csv_path)
        else:
            outputs[key] = pd.DataFrame()

    return outputs


if __name__ == "__main__":
    data = run_discovery()
    for source, df in data.items():
        print(f"\n{source.upper()} – {len(df)} rows")
        if not df.empty:
            print(df.head())