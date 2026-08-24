import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

PAGASA_URL = "https://pagasa.dost.gov.ph/weather"
OUTPUT_FILE = "feed.xml"


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


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


def extract_weather(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    # Extract Synopsis
    match = re.search(
        r"Synopsis\s+(.*?)(?=\s+Forecast Weather Conditions)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if not match:
        raise RuntimeError("Could not find PAGASA Synopsis.")

    synopsis = clean_text(match.group(1))

    # Extract issued time if available
    issued_match = re.search(
        r"Issued at:\s*(.*?)(?=\s+Synopsis)",
        text,
        re.DOTALL | re.IGNORECASE
    )

    issued = clean_text(issued_match.group(1)) if issued_match else ""

    return issued, synopsis


def generate_rss(issued, synopsis):
    now = datetime.now(timezone.utc)

    title = f"PAGASA Daily Weather - {issued}"

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>PAGASA Daily Weather Synopsis</title>
        <link>{PAGASA_URL}</link>
        <description>Daily weather synopsis from PAGASA</description>
        <lastBuildDate>{format_datetime(now)}</lastBuildDate>

        <item>
            <title>{escape(title)}</title>
            <description>{escape(synopsis)}</description>
            <link>{PAGASA_URL}</link>
            <guid isPermaLink="false">{escape(issued)}</guid>
            <pubDate>{format_datetime(now)}</pubDate>
        </item>
    </channel>
</rss>
"""

    Path(OUTPUT_FILE).write_text(rss, encoding="utf-8")


def main():
    print("Fetching PAGASA...")

    html = get_pagasa_page()

    print("PAGASA page downloaded.")

    issued, synopsis = extract_weather(html)

    print("\n========== PAGASA SYNOPSIS ==========\n")
    print(synopsis)
    print("\n=====================================")

    generate_rss(issued, synopsis)

    print("\nRSS feed generated: feed.xml")


if __name__ == "__main__":
    main()
 
