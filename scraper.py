import requests
from bs4 import BeautifulSoup
import re

PAGASA_URL = "https://pagasa.dost.gov.ph/weather"


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    print("Fetching PAGASA...")

    response = requests.get(
        PAGASA_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 PAGASA Weather Bot"
        }
    )

    response.raise_for_status()

    print("PAGASA page downloaded.")
    print("Page size:", len(response.text), "bytes")

    soup = BeautifulSoup(response.text, "html.parser")

    text = soup.get_text("\n", strip=True)

    print("\nLooking for Synopsis...")

    match = re.search(
        r"Synopsis\s+(.*?)(?=\s+Forecast Weather Conditions)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if not match:
        print("ERROR: Could not find Synopsis.")
        return

    synopsis = clean_text(match.group(1))

    print("\n========== PAGASA SYNOPSIS ==========\n")
    print(synopsis)
    print("\n=====================================")


if __name__ == "__main__":
    main()
 
