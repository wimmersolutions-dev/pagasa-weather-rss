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

# Keep the latest 7 reports in the RSS feed.
MAX_ITEMS = 7


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    """
    Clean excessive whitespace from text.
    """

    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# DOWNLOAD PAGASA PAGE
# ============================================================

def get_pagasa_page():
    """
    Download the PAGASA weather page.
    """

    response = requests.get(
        PAGASA_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 PAGASA Weather Bot"
        }
    )

    response.raise_for_status()

    return response.text


# ============================================================
# EXTRACT WEATHER INFORMATION
# ============================================================

def extract_weather(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # --------------------------------------------------------
    # Convert page to text for Synopsis / Issued time.
    # --------------------------------------------------------

    text = soup.get_text(
        "\n",
        strip=True
    )

    # ========================================================
    # SYNOPSIS
    # ========================================================

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

        raise RuntimeError(
            "Could not find PAGASA Synopsis."
        )

    synopsis = clean_text(
        synopsis_match.group(1)
    )

    # ========================================================
    # ISSUED TIME
    # ========================================================

    issued_match = re.search(
        r"Issued at:\s*(.*?)(?=\s+Synopsis)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if issued_match:

        issued = clean_text(
            issued_match.group(1)
        )

    else:

        issued = ""

        # ========================================================
    # FIND FORECAST WEATHER CONDITIONS SECTION
    # ========================================================

    forecast_heading = soup.find(
        string=re.compile(
            r"Forecast Weather Conditions",
            re.IGNORECASE
        )
    )

    if not forecast_heading:
        raise RuntimeError(
            "Could not find Forecast Weather Conditions heading."
        )

    print("\n========== FORECAST DEBUG ==========\n")

    print(
        "Found heading:",
        repr(forecast_heading.strip())
    )

    # Show the HTML structure around the heading.
    current = forecast_heading.parent

    for level in range(1, 7):

        if current is None:
            break

        print(
            f"\n--- Parent level {level}: "
            f"{current.name} ---"
        )

        print(
            str(current)[:3000]
        )

        current = current.parent

    print(
        "\n========== END FORECAST DEBUG ==========\n"
    )

    raise RuntimeError(
        "Diagnostic run complete. "
        "Check the GitHub Action log above."
    )

    
    # ========================================================
    # FIND THE TABLE
    # ========================================================

    forecast_table = None

    # First attempt:
    # Check if the heading is inside a table.

    parent_table = forecast_heading.find_parent(
        "table"
    )

    if parent_table:

        forecast_table = parent_table

    # Second attempt:
    # Find the next table after the heading.

    if forecast_table is None:

        parent = forecast_heading.parent

        if parent:

            forecast_table = parent.find_next(
                "table"
            )

    # Third attempt:
    # Search nearby elements for the first table.

    if forecast_table is None:

        for element in forecast_heading.parents:

            forecast_table = element.find_next(
                "table"
            )

            if forecast_table:

                break

    if forecast_table is None:

        raise RuntimeError(
            "Could not find Forecast Weather Conditions table."
        )

    # ========================================================
    # READ TABLE ROWS
    # ========================================================

    rows = forecast_table.find_all(
        "tr"
    )

    forecast_rows = []

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = []

        for cell in cells:

            value = clean_text(
                cell.get_text(
                    " ",
                    strip=True
                )
            )

            if value:

                values.append(
                    value
                )

        # Ignore empty rows.

        if not values:

            continue

        # ----------------------------------------------------
        # Skip table header.
        # ----------------------------------------------------

        header_text = " ".join(
            value.lower()
            for value in values
        )

        if (
            "place" in header_text
            and "weather" in header_text
        ):

            continue

        forecast_rows.append(
            values
        )

    if not forecast_rows:

        raise RuntimeError(
            "Forecast Weather Conditions table is empty."
        )

    # ========================================================
    # FORMAT FORECAST
    # ========================================================

    formatted_forecast = []

    for index, row in enumerate(
        forecast_rows,
        start=1
    ):

        place = (
            row[0]
            if len(row) > 0
            else ""
        )

        weather = (
            row[1]
            if len(row) > 1
            else ""
        )

        cause = (
            row[2]
            if len(row) > 2
            else ""
        )

        impacts = (
            row[3]
            if len(row) > 3
            else ""
        )

        formatted_row = (
            f"{index}. PLACE:\n"
            f"{place}\n\n"
            f"WEATHER CONDITION:\n"
            f"{weather}\n\n"
            f"CAUSED BY:\n"
            f"{cause}\n\n"
            f"IMPACTS:\n"
            f"{impacts}"
        )

        formatted_forecast.append(
            formatted_row
        )

    forecast = "\n\n".join(
        formatted_forecast
    )

    return (
        issued,
        synopsis,
        forecast
    )


# ============================================================
# LOAD EXISTING RSS ITEMS
# ============================================================

def load_existing_items():

    path = Path(
        OUTPUT_FILE
    )

    if not path.exists():

        return []

    try:

        tree = ET.parse(
            path
        )

        root = tree.getroot()

        items = []

        for item in root.findall(
            "./channel/item"
        ):

            title = item.findtext(
                "title",
                ""
            )

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

            items.append(
                {
                    "title": title,
                    "description": description,
                    "link": link,
                    "guid": guid,
                    "pubDate": pub_date
                }
            )

        return items

    except Exception as error:

        print(
            "Could not read existing RSS:",
            error
        )

        return []


# ============================================================
# GENERATE RSS FEED
# ============================================================

def generate_rss(
    issued,
    synopsis,
    forecast
):

    now = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # Unique ID for the PAGASA report.
    # --------------------------------------------------------

    guid = (
        f"pagasa-{clean_text(issued)}"
    )

    # --------------------------------------------------------
    # RSS description.
    # --------------------------------------------------------

    description = (
        "[SYNOPSIS]\n\n"
        f"{synopsis}\n\n"
        "[FORECAST WEATHER CONDITIONS]\n\n"
        f"{forecast}"
    )

    new_item = {

        "title":
            f"PAGASA Daily Weather - {issued}",

        "description":
            description,

        "link":
            PAGASA_URL,

        "guid":
            guid,

        "pubDate":
            format_datetime(now)
    }

    # --------------------------------------------------------
    # Load existing RSS items.
    # --------------------------------------------------------

    existing_items = (
        load_existing_items()
    )

    existing_guids = {
        item["guid"]
        for item in existing_items
    }

    # --------------------------------------------------------
    # Add new item if it doesn't already exist.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Keep only the latest 7 reports.
    # --------------------------------------------------------

    existing_items = (
        existing_items[:MAX_ITEMS]
    )

    # ========================================================
    # BUILD RSS XML
    # ========================================================

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
            PAGASA Daily Weather
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

    Path(
        OUTPUT_FILE
    ).write_text(
        rss,
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=========================================="
    )

    print(
        "          PAGASA WEATHER SCRAPER"
    )

    print(
        "=========================================="
    )

    print()

    # --------------------------------------------------------
    # Download PAGASA.
    # --------------------------------------------------------

    print(
        "Fetching PAGASA..."
    )

    html = get_pagasa_page()

    print(
        "PAGASA page downloaded."
    )

    print()

    # --------------------------------------------------------
    # Extract information.
    # --------------------------------------------------------

    (
        issued,
        synopsis,
        forecast
    ) = extract_weather(
        html
    )

    # ========================================================
    # DISPLAY SYNOPSIS
    # ========================================================

    print(
        "Issued:",
        issued
    )

    print()

    print(
        "=============== SYNOPSIS ==============="
    )

    print()

    print(
        synopsis
    )

    print()

    # ========================================================
    # DISPLAY FORECAST
    # ========================================================

    print(
        "======= FORECAST WEATHER CONDITIONS ======="
    )

    print()

    print(
        forecast
    )

    print()

    print(
        "==========================================="
    )

    # ========================================================
    # CREATE RSS
    # ========================================================

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


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":

    main()
 
