import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import format_datetime
import re
from pathlib import Path

PAGASA_URL = "https://pagasa.dost.gov.ph/weather"
OUTPUT_FILE = "feed.xml"


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def get_pagasa_page():
    response = requests.get(
        PAGASA_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 PAGASA Weather RSS Bot"
        }
    )

    response.raise_for_status()
    return response.text


def extract_weather(html):
    soup = BeautifulSoup(html, "html.parser")

    # Get all visible text from the page.
    text = soup.get_text("\n", strip=True)

    # Find the Synopsis section.
    match = re.search(
        r"Synopsis\s+(.*?)(?=\s+Forecast Weather Conditions|\s+TC Information|\s+Forecast Wind and Coastal Water Conditions)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if not match:
        raise RuntimeError("Could not find PAGASA Synopsis section.")

    synopsis = clean_text(match.group(1))

    # Find the issued time.
    issued_match = re.search(
        r"Issued at:\s*(.*?)(?=\s+Synopsis)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    issued = clean_text(issued_match.group(1)) if issued_match else ""

    return issued, synopsis


def escape_xml(text):
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def generate_rss(issued, synopsis):
    now = datetime.now().astimezone()

    title = f"PAGASA Daily Weather - {issued}"

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>PAGASA Daily Weather Synopsis</title>
        <link>{PAGASA_URL}</link>
        <description>Daily weather synopsis from PAGASA</description>
        <lastBuildDate>{format_datetime(now)}</lastBuildDate>

        <item>
            <title>{escape_xml(title)}</title>
            <description>{escape_xml(synopsis)}</description>
            <link>{PAGASA_URL}</link>
            <guid isPermaLink="false">{escape_xml(issued)}</guid>
            <pubDate>{format_datetime(now)}</pubDate>
        </item>
    </channel>
</rss>
"""

    Path(OUTPUT_FILE).write_text(rss, encoding="utf-8")


def main():
    print("Fetching PAGASA...")

    html = get_pagasa_page()

    issued, synopsis = extract_weather(html)

    print("Issued:", issued)
    print("Synopsis:", synopsis)

    generate_rss(issued, synopsis)

    print("RSS generated successfully.")


if __name__ == "__main__":
    main()
 
