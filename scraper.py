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


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# DOWNLOAD PAGASA PAGE
# ============================================================

def get_pagasa_page():

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
# EXTRACT WEATHER
# ============================================================

def extract_weather(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # ========================================================
    # SYNOPSIS
    # ========================================================

    text = soup.get_text(
        "\n",
        strip=True
    )

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

    issued = (
        clean_text(issued_match.group(1))
        if issued_match
        else ""
    )

    # ========================================================
    # FIND FORECAST WEATHER CONDITIONS HEADING
    # ========================================================

    forecast_heading = soup.find(
        string=re.compile(
            r"^\s*Forecast Weather Conditions\s*$",
            re.IGNORECASE
        )
    )

    if not forecast_heading:

        raise RuntimeError(
            "Could not find Forecast Weather Conditions heading."
        )

    # ========================================================
    # FIND THE TABLE ASSOCIATED WITH THE HEADING
    # ========================================================

    forecast_table = None

    # Walk through the heading's parents.
    # We stop as soon as we find the first table.
    current = forecast_heading.parent

    while current is not None:

        table = current.find(
            "table"
        )

        if table is not None:

            forecast_table = table
            break

        current = current.parent

    # If the heading itself is not inside the container
    # containing the table, look at the next table after
    # the heading.

    if forecast_table is None:

        forecast_table = forecast_heading.find_next(
            "table"
        )

    if forecast_table is None:

        raise RuntimeError(
            "Could not find Forecast Weather Conditions table."
        )

    print(
        "Forecast Weather Conditions table found."
    )

    # ========================================================
    # READ ONLY THIS TABLE
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
                values.append(value)

        if not values:
            continue

        # Skip the header row.
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
    # FORMAT FORECAST TABLE
    # ========================================================

    formatted_rows = []

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

        caused_by = (
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
            f"{caused_by}\n\n"
            f"IMPACTS:\n"
            f"{impacts}"
        )

        formatted_rows.append(
            formatted_row
        )

    forecast = "\n\n".join(
        formatted_rows
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

            items.append(
                {
                    "title": item.findtext(
                        "title",
                        ""
                    ),

                    "description": item.findtext(
                        "description",
                        ""
                    ),

                    "link": item.findtext(
                        "link",
                        PAGASA_URL
                    ),

                    "guid": item.findtext(
                        "guid",
                        ""
                    ),

                    "pubDate": item.findtext(
                        "pubDate",
                        ""
                    )
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
# GENERATE RSS
# ============================================================

def generate_rss(
    issued,
    synopsis,
    forecast
):

    now = datetime.now(
        timezone.utc
    )

    # Unique ID based on PAGASA issue time.
    guid = (
        f"pagasa-{clean_text(issued)}"
    )

    # Keep Synopsis and Forecast clearly separated.
    description = (
        "[SYNOPSIS]\n\n"
        f"{synopsis}\n\n\n"
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

    # Load existing RSS history.
    existing_items = (
        load_existing_items()
    )

    existing_guids = {
        item["guid"]
        for item in existing_items
    }

    # Add only if this report is new.
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

    # Keep latest 7 reports.
    existing_items = (
        existing_items[:MAX_ITEMS]
    )

    # ========================================================
    # BUILD XML
    # ========================================================

    items_xml = ""

    for item in existing_items:

        items_xml += f"""
        <item>
            <title>{escape(item["title"])}</title>
            <description>{escape(item["description"])}</description>
            <link>{escape(item["link"])}</link>
            <guid isPermaLink="false">{escape(item["guid"])}</guid>
            <pubDate>{escape(item["pubDate"])}</pubDate>
        </item>
        """

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>

<rss version="2.0">

    <channel>

        <title>PAGASA Daily Weather</title>

        <link>{PAGASA_URL}</link>

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

    # ========================================================
    # SHOW SYNOPSIS
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
    # SHOW FORECAST
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
    # GENERATE RSS
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


if __name__ == "__main__":

    main()
 
