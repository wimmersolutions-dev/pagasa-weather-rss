import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

PAGASA_URL = "https://pagasa.dost.gov.ph/weather"
OUTPUT_FILE = "feed.xml"
MAX_ITEMS = 7


def clean_text(text):
    """Remove excessive whitespace and clean the text."""
    return re.sub(r"\s+", " ", text).strip()


def get_pagasa_page():
    """Download the PAGASA weather page."""

    response = requests.get(
        PAGASA_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 PAGASA Weather Bot"
        }
    )

    response.raise_for_status()

    return response.text


def extract_weather(html):
    """Extract Synopsis and Forecast Weather Conditions."""

    soup = BeautifulSoup(html, "html.parser")

    # Convert the page into plain text.
    text = soup.get_text("\n", strip=True)

    # ---------------------------------------------------------
    # SYNOPSIS
    # ---------------------------------------------------------

    synopsis_match = re.search(
        r"Synopsis\s*"
        r"(.*?)"
        r"(?=\s*(?:Tropical Cyclone Information|"
        r"Tropical Cyclone|"
        r"TC Information|"
        r"Forecast Weather Conditions))",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if not synopsis_match:
        raise RuntimeError("Could not find PAGASA Synopsis.")

    synopsis = clean_text(synopsis_match.group(1))

    # ---------------------------------------------------------
    # FORECAST WEATHER CONDITIONS
    # ---------------------------------------------------------

    forecast_match = re.search(
        r"Forecast Weather Conditions\s*"
        r"(.*?)"
        r"(?=\s*(?:Forecast Wind and Coastal Water Conditions|"
        r"Tropical Cyclone Information|"
        r"Tropical Cyclone|"
        r"TC Information|"
        r"Hourly Forecast|"
        r"Satellite Images|"
        r"Weather Advisory))",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if not forecast_match:
        raise RuntimeError(
            "Could not find Forecast Weather Conditions."
        )

    forecast = clean_text(forecast_match.group(1))

    # ---------------------------------------------------------
    # ISSUED TIME
    # ---------------------------------------------------------

    issued_match = re.search(
        r"Issued at:\s*(.*?)(?=\s+Synopsis)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    issued = (
        clean_text(issued_match.group(1))
        if issued_match
        else ""
    )

    return issued, synopsis, forecast


def load_existing_items():
    """Load existing RSS items so we can keep a history."""

    path = Path(OUTPUT_FILE)

    if not path.exists():
        return []

    try:
        tree = ET.parse(path)

        root = tree.getroot()

        items = []

        for item in root.findall("./channel/item"):

            title = item.findtext("title", "")

            description = item.findtext(
                "description",
                ""
            )

            link = item.findtext(
                "link",
                PAGASA_URL
            )

            guid = item.findtext(
                "guid",
                ""
            )

            pub_date = item.findtext(
                "pubDate",
                ""
            )

            items.append({
                "title": title,
                "description": description,
                "link": link,
                "guid": guid,
                "pubDate": pub_date
            })

        return items

    except Exception as e:

        print(
            "Could not read existing RSS:",
            e
        )

        return []


def generate_rss(
    issued,
    synopsis,
    forecast
):
    """Generate the RSS feed."""

    now = datetime.now(timezone.utc)

    # Create a unique ID for this PAGASA report.
    guid = f"pagasa-{clean_text(issued)}"

    # ---------------------------------------------------------
    # RSS DESCRIPTION
    # ---------------------------------------------------------

    description = (
        "[SYNOPSIS]\n\n"
        f"{synopsis}\n\n"
        "[FORECAST WEATHER CONDITIONS]\n\n"
        f"{forecast}"
    )

    new_item = {
        "title": f"PAGASA Daily Weather - {issued}",

        "description": description,

        "link": PAGASA_URL,

        "guid": guid,

        "pubDate": format_datetime(now)
    }

    # Get existing RSS items.
    existing_items = load_existing_items()

    existing_guids = {
        item["guid"]
        for item in existing_items
    }

    # Don't add the same report twice.
    if guid not in existing_guids:

        existing_items.insert(
            0,
            new_item
        )

        print(
            "New PAGASA report added."
        )

    else:

        print(
            "This PAGASA report already exists."
        )

    # Keep only the latest 7 reports.
    existing_items = existing_items[:MAX_ITEMS]

    # ---------------------------------------------------------
    # BUILD RSS XML
    # ---------------------------------------------------------

    items_xml = ""

    for item in existing_items:

        items_xml += f"""
        <item>
            <title>{escape(item["title"])}</title>

            <description>
                {escape(item["description"])}
            </description>

            <link>{escape(item["link"])}</link>

            <guid isPermaLink="false">
                {escape(item["guid"])}
            </guid>

            <pubDate>
                {escape(item["pubDate"])}
            </pubDate>
        </item>
        """

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>

<rss version="2.0">

    <channel>

        <title>
            PAGASA Daily Weather Synopsis
        </title>

        <link>
            {PAGASA_URL}
        </link>

        <description>
            Daily weather information from PAGASA
        </description>

        <lastBuildDate>
            {format_datetime(now)}
        </lastBuildDate>

        {items_xml}

    </channel>

</rss>
"""

    Path(OUTPUT_FILE).write_text(
        rss,
        encoding="utf-8"
    )


def main():

    print(
        "====================================="
    )

    print(
        "       PAGASA WEATHER SCRAPER"
    )

    print(
        "====================================="
    )

    print()

    print(
        "Fetching PAGASA..."
    )

    html = get_pagasa_page()

    print(
        "PAGASA page downloaded."
    )

    print()

    issued, synopsis, forecast = (
        extract_weather(html)
    )

    # ---------------------------------------------------------
    # DISPLAY RESULTS
    # ---------------------------------------------------------

    print(
        "Issued:",
        issued
    )

    print()

    print(
        "========== SYNOPSIS =========="
    )

    print()

    print(
        synopsis
    )

    print()

    print(
        "===== FORECAST WEATHER CONDITIONS ====="
    )

    print()

    print(
        forecast
    )

    print()

    print(
        "========================================"
    )

    # ---------------------------------------------------------
    # GENERATE RSS
    # ---------------------------------------------------------

    generate_rss(
        issued,
        synopsis,
        forecast
    )

    print()

    print(
        "RSS feed generated successfully."
    )

    print(
        "File:",
        OUTPUT_FILE
    )


if __name__ == "__main__":

    main()
 
