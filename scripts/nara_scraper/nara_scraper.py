"""
NARA Catalog Scraper — Apollo Missions Film Reels (Series 133360601)

Scrapes metadata for all items in:
  https://catalog.archives.gov/search-within/133360601

Uses Selenium (headless Chrome) to render the JS-heavy NARA catalog pages,
then parses the HTML with BeautifulSoup.

Output: nara_apollo_metadata.json
"""

import json
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

console = Console()

SERIES_NAID = "133360601"
SEARCH_WITHIN_URL = f"https://catalog.archives.gov/search-within/{SERIES_NAID}"
ITEM_BASE_URL = "https://catalog.archives.gov/id"
OUTPUT_FILE = "nara_apollo_metadata.json"
PAGE_LOAD_WAIT = 6  # seconds to let JS render


# ── Selenium helpers ────────────────────────────────────────────────────────

def get_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Suppress logging noise
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    return webdriver.Chrome(options=options)


def load_page(driver: webdriver.Chrome, url: str, wait_seconds: float = PAGE_LOAD_WAIT) -> BeautifulSoup:
    """Navigate to *url*, wait for JS to render, return a BeautifulSoup."""
    driver.get(url)
    time.sleep(wait_seconds)
    return BeautifulSoup(driver.page_source, "html.parser")


# ── Phase 1: Collect all item NAIDs from the search-within listing ──────────

def collect_item_naids(driver: webdriver.Chrome) -> list[dict]:
    """
    Paginate through the search-within results and collect basic info
    (NAID, title, local_id) for every item.
    """
    items: list[dict] = []
    page = 1

    # First load to get total count
    url = f"{SEARCH_WITHIN_URL}?page={page}"
    soup = load_page(driver, url)

    # Parse total results — text like "1–20 of 182 results"
    total = _parse_total_results(soup)
    console.print(f"[bold green]Total items to scrape: {total}[/bold green]")

    per_page = 20  # NARA default
    total_pages = (total + per_page - 1) // per_page if total else 10

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Collecting item list…", total=total_pages)

        while True:
            page_items = _parse_search_results(soup)
            if not page_items:
                break
            items.extend(page_items)
            progress.update(task, advance=1)

            page += 1
            if page > total_pages:
                break

            url = f"{SEARCH_WITHIN_URL}?page={page}"
            soup = load_page(driver, url)

    console.print(f"[bold]Collected {len(items)} item stubs from {page - 1} pages.[/bold]")
    return items


def _parse_total_results(soup: BeautifulSoup) -> int:
    """Extract the total result count from the search page."""
    for el in soup.find_all(string=re.compile(r"of\s+\d+\s+results?")):
        m = re.search(r"of\s+(\d+)\s+results?", el)
        if m:
            return int(m.group(1))
    return 0


def _parse_search_results(soup: BeautifulSoup) -> list[dict]:
    """Parse one page of search-within results into stub dicts."""
    items = []
    for card in soup.find_all("div", class_="search-result"):
        item: dict = {}

        # Title + link
        link = card.find("a", class_="result-link")
        if link:
            item["title"] = link.get_text(strip=True)
            href = link.get("href", "")
            m = re.search(r"/id/(\d+)", href)
            if m:
                item["naid"] = m.group(1)

        # NAID (also in card text)
        naid_el = card.find(attrs={"data-testid": re.compile(r"nac-result_naId")})
        if naid_el and "naid" not in item:
            item["naid"] = naid_el.get_text(strip=True)

        # Local ID
        local_el = card.find(attrs={"data-testid": re.compile(r"nac-result_id-")})
        if local_el:
            item["local_id"] = local_el.get_text(strip=True)

        if item.get("naid"):
            items.append(item)

    return items


# ── Phase 2: Scrape full metadata from each item page ──────────────────────

def scrape_item_metadata(driver: webdriver.Chrome, naid: str) -> dict:
    """Load an individual item page and extract all available metadata."""
    url = f"{ITEM_BASE_URL}/{naid}"
    soup = load_page(driver, url)

    meta: dict = {"naid": naid, "url": url}

    # Title
    title_el = soup.find(attrs={"data-testid": "nac-page-header--title"})
    if title_el:
        meta["title"] = title_el.get_text(strip=True)

    # Scope / description (if present)
    scope_el = soup.find(attrs={"data-testid": re.compile(r"nac-description__scope")})
    if scope_el:
        meta["description"] = _clean_description(scope_el.get_text(strip=True))
    else:
        # Some items put description inline before breadcrumbs
        desc_el = soup.find(attrs={"data-testid": "nac-description__description"})
        if desc_el:
            meta["description"] = _clean_description(desc_el.get_text(strip=True))

    # Dates
    dates_el = soup.find(attrs={"data-testid": "nac-description__dates"})
    if dates_el:
        date_items = []
        for li in dates_el.find_all("li"):
            date_items.append(li.get_text(strip=True))
        meta["dates"] = date_items if date_items else [dates_el.get_text(strip=True)]

    # Access restriction
    access_el = soup.find(attrs={"data-testid": "nac-description__access"})
    if access_el:
        meta["access"] = access_el.get_text(strip=True).replace("Access:", "").strip().rstrip(",")

    # Use restriction
    use_el = soup.find(attrs={"data-testid": "nac-description__use"})
    if use_el:
        specific = soup.find(attrs={"data-testid": "nac-description__use--specific"})
        note = soup.find(attrs={"data-testid": "nac-description__use--note"})
        meta["use_restriction"] = {
            "status": use_el.find("h2").get_text(strip=True).replace("Use:", "").strip().rstrip(",") if use_el.find("h2") else "",
            "type": specific.get_text(strip=True) if specific else "",
            "note": note.get_text(strip=True) if note else "",
        }

    # Creator
    creator_el = soup.find(attrs={"data-testid": "nac-description__creators--most-recent"})
    if creator_el:
        meta["creator"] = creator_el.get_text(strip=True).replace("Most Recent,", "").strip().rstrip(",")

    # ── Control Numbers ──
    # National Archives Identifier
    nai_el = soup.find(attrs={"data-testid": "nac-description__control-numbers--national-archives-identifier"})
    if nai_el:
        meta["national_archives_identifier"] = _extract_value(nai_el)

    # Local Identifier
    lid_el = soup.find(attrs={"data-testid": "nac-description__control-numbers--local-identifier"})
    if lid_el:
        meta["local_identifier"] = _extract_value(lid_el)

    # Agency-Assigned Identifiers (may have multiple)
    aa_el = soup.find(attrs={"data-testid": "nac-description__control-numbers--agency-assigned-identifier"})
    if aa_el:
        agency_ids = []
        for li in aa_el.find_all("li"):
            id_value = ""
            note_text = ""
            # The ID value is in the first span.display-block
            val_span = li.find("span", class_="display-block")
            if val_span:
                # Get text but exclude the asterisk span
                for child in val_span.children:
                    if isinstance(child, str):
                        id_value += child.strip()
            # The note is in the div with italic text
            for div in li.find_all("div"):
                div_classes = div.get("class", [])
                if "text-italic" in div_classes:
                    note_text = div.get_text(strip=True).lstrip("*").strip()
                    break
            agency_ids.append({"value": id_value, "note": note_text})
        meta["agency_assigned_identifiers"] = agency_ids

    # ── Object / reel info ──
    obj_el = soup.find(attrs={"data-testid": "nac-object-view--designator-and-description"})
    if obj_el:
        meta["object_designator"] = obj_el.get_text(strip=True)

    # ── Archived copies location ──
    copies_el = soup.find(attrs={"data-testid": "nac-description__section-archived-copies--contact"})
    if copies_el:
        loc_text = copies_el.get_text(strip=True)
        # Extract location name
        m = re.search(r"Archived Copy Location:\s*(.+?)(?:Access|$)", loc_text)
        if m:
            meta["archived_copy_location"] = m.group(1).strip()

    # ── Digital objects / files ──
    meta["digital_objects"] = _extract_digital_objects(soup)

    # ── Part of (hierarchy) ──
    partof_el = soup.find(attrs={"data-testid": "nac-description__from"})
    if partof_el:
        rg_el = soup.find(attrs={"data-testid": "nac-description__from--recordGroup"})
        series_el = soup.find(attrs={"data-testid": "nac-description__from--series"})
        hierarchy = {}
        if rg_el:
            rg_num = soup.find(attrs={"data-testid": "nac-result_ancestor-number"})
            rg_title = rg_el.find(attrs={"data-testid": "nac-result_ancestor-title"})
            rg_num_text = rg_num.get_text(strip=True) if rg_num else ""
            # Strip "Record Group" prefix to get just the number
            rg_num_text = re.sub(r"^Record\s+Group\s*", "", rg_num_text).strip()
            hierarchy["record_group"] = {
                "number": rg_num_text,
                "title": rg_title.get_text(strip=True) if rg_title else "",
            }
        if series_el:
            s_title = series_el.find(attrs={"data-testid": "nac-result_ancestor-title"})
            hierarchy["series"] = s_title.get_text(strip=True) if s_title else ""
        meta["part_of"] = hierarchy

    # ── Tags & comments counts ──
    tags_btn = soup.find(attrs={"data-testid": "nac-object-viewer--tag-panel-button"})
    if tags_btn:
        m = re.search(r"(\d+)", tags_btn.get_text())
        meta["tag_count"] = int(m.group(1)) if m else 0

    comments_btn = soup.find(attrs={"data-testid": "nac-object-viewer--comment-panel-button"})
    if comments_btn:
        m = re.search(r"(\d+)", comments_btn.get_text())
        meta["comment_count"] = int(m.group(1)) if m else 0

    return meta


def _clean_description(text: str) -> str:
    """Remove leading 'Description' label from description text."""
    text = re.sub(r"^Description\s*", "", text).strip()
    return text


def _extract_value(el) -> str:
    """Extract the primary value text from a control-number element."""
    strong = el.find("strong")
    if strong:
        return strong.get_text(strip=True)
    # Fallback: first text content
    text = el.get_text(strip=True)
    # Remove labels
    for label in ("National Archives Identifier", "Local Identifier", ","):
        text = text.replace(label, "")
    return text.strip()


def _extract_digital_objects(soup: BeautifulSoup) -> list[dict]:
    """
    Extract info about digital objects (video files, PDFs, etc.) linked
    on the item page.
    """
    objects = []
    # Look for download button area or object list
    # The object viewer shows one at a time; check for multiple object selectors
    # Look for the object list / thumbnails
    thumb_els = soup.find_all(attrs={"data-testid": re.compile(r"nac-object-viewer--thumbnail")})
    for thumb in thumb_els:
        obj: dict = {}
        testid = thumb.get("data-testid", "")
        # May have title attribute
        title_attr = thumb.get("title", "")
        if title_attr:
            obj["description"] = title_attr
        objects.append(obj)

    # Look for download links
    dl_btn = soup.find(attrs={"data-testid": "nac-object-viewer--download-button"})
    if dl_btn:
        link = dl_btn.find("a", href=True) if dl_btn.name != "a" else dl_btn
        if link and link.get("href"):
            if not objects:
                objects.append({})
            objects[0]["download_url"] = link["href"]

    # Also look for linked documents (shot lists / PDFs) in a different section
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.endswith(".pdf") or "shotlist" in href.lower() or "shot-list" in href.lower():
            objects.append({
                "type": "document",
                "url": href,
                "text": a_tag.get_text(strip=True),
            })

    return objects


# ── Main workflow ────────────────────────────────────────────────────────────

def main():
    console.print("[bold cyan]NARA Apollo Missions Film Reel Metadata Scraper[/bold cyan]")
    console.print(f"Series: {SERIES_NAID}")
    console.print()

    # Check for partial progress
    partial_path = Path(OUTPUT_FILE + ".partial")
    already_scraped: dict[str, dict] = {}
    if partial_path.exists():
        with open(partial_path, "r", encoding="utf-8") as f:
            already_scraped = {item["naid"]: item for item in json.load(f)}
        console.print(f"[yellow]Resuming – {len(already_scraped)} items already scraped.[/yellow]")

    driver = get_driver()
    try:
        # Phase 1 – collect all item NAIDs
        console.print("[bold]Phase 1: Collecting item list from search results…[/bold]")
        item_stubs = collect_item_naids(driver)

        if not item_stubs:
            console.print("[red]No items found! Check the URL or page structure.[/red]")
            return

        # Phase 2 – scrape metadata for each item
        console.print()
        console.print("[bold]Phase 2: Scraping detailed metadata for each item…[/bold]")

        results: list[dict] = list(already_scraped.values())
        to_scrape = [s for s in item_stubs if s["naid"] not in already_scraped]
        console.print(f"  Items remaining: {len(to_scrape)} of {len(item_stubs)}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scraping items…", total=len(to_scrape))

            for i, stub in enumerate(to_scrape):
                naid = stub["naid"]
                try:
                    meta = scrape_item_metadata(driver, naid)
                    results.append(meta)
                except Exception as exc:
                    console.print(f"[red]  Error scraping NAID {naid}: {exc}[/red]")
                    results.append({"naid": naid, "error": str(exc)})

                progress.update(task, advance=1)

                # Save partial progress every 10 items
                if (i + 1) % 10 == 0:
                    _save_json(partial_path, results)

        # Final save
        _save_json(Path(OUTPUT_FILE), results)
        # Clean up partial
        if partial_path.exists():
            partial_path.unlink()

        console.print()
        console.print(f"[bold green]Done! {len(results)} items saved to {OUTPUT_FILE}[/bold green]")

    finally:
        driver.quit()


def _save_json(path: Path, data: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
