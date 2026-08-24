def extract_weather(html):
    soup = BeautifulSoup(html, "html.parser")

    # =========================================================
    # SYNOPSIS
    # =========================================================

    text = soup.get_text("\n", strip=True)

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

    # =========================================================
    # ISSUED TIME
    # =========================================================

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

    # =========================================================
    # FORECAST WEATHER CONDITIONS TABLE
    # =========================================================

    forecast_heading = soup.find(
        string=re.compile(
            r"Forecast Weather Conditions",
            re.IGNORECASE
        )
    )

    if not forecast_heading:
        raise RuntimeError(
            "Could not find Forecast Weather Conditions."
        )

    # Find the table associated with the section.
    forecast_table = forecast_heading.find_parent(
        "table"
    )

    # Sometimes the heading is outside the table.
    if not forecast_table:

        parent = forecast_heading.parent

        if parent:
            forecast_table = parent.find_next(
                "table"
            )

    if not forecast_table:
        raise RuntimeError(
            "Could not find Forecast Weather Conditions table."
        )

    rows = forecast_table.find_all("tr")

    forecast_rows = []

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in cells
        ]

        values = [
            value
            for value in values
            if value
        ]

        if len(values) < 2:
            continue

        # Skip table header.
        header_text = " ".join(
            value.lower()
            for value in values
        )

        if (
            "place" in header_text
            and "weather" in header_text
        ):
            continue

        forecast_rows.append(values)

    if not forecast_rows:
        raise RuntimeError(
            "Forecast Weather Conditions table is empty."
        )

    # =========================================================
    # FORMAT TABLE
    # =========================================================

    formatted_forecast = []

    for index, row in enumerate(
        forecast_rows,
        start=1
    ):

        place = row[0] if len(row) > 0 else ""
        weather = row[1] if len(row) > 1 else ""
        cause = row[2] if len(row) > 2 else ""
        impacts = row[3] if len(row) > 3 else ""

        formatted_forecast.append(
            f"""
{index}. PLACE:
{place}

WEATHER CONDITION:
{weather}

CAUSED BY:
{cause}

IMPACTS:
{impacts}
""".strip()
        )

    forecast = "\n\n".join(
        formatted_forecast
    )

    return issued, synopsis, forecast
 
