"""
transcript.py  —  Phase 2: Lecture transcript extraction and saving.

Public API
----------
get_transcript(driver, lecture, module_number) -> dict
    Navigate to a lecture page, open the Transcript panel, and return
    the transcript text plus metadata.

save_transcript(result, course_slug, output_dir) -> Optional[Path]
    Write a transcript result to a UTF-8 text file under:
        <output_dir>/transcripts/<course_slug>/<module_number>/<slug>.txt
    Returns the path written to, or None when skipped.

DOM structure (verified from live authenticated session, 2026-09-30)
--------------------------------------------------------------------
Transcript button (toolbar):
    button[data-testid="item-tool-panel-button-transcript"]
    aria-pressed="false" when closed, "true" when open.

Transcript panel container (visible when panel is open):
    div[data-testid="item-tool-panel-layout-tool-content-panel-content"]

Transcript text is inside span.rc-Phrase elements, each with:
    aria-label="play video from <spoken text here>"
    role="button"

Paragraphs are grouped under div.rc-Paragraph, each preceded by a
visible timestamp button (e.g., "0:09", "1:15").

No virtualization was observed for tested lectures; all phrases are
rendered in the initial DOM once the panel is opened.
"""

import re
from pathlib import Path
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# ── Stable selectors (data-testid, not generated css-* names) ────────────────

_BTN_TRANSCRIPT = "[data-testid='item-tool-panel-button-transcript']"
_PANEL_CONTENT  = "[data-testid='item-tool-panel-layout-tool-content-panel-content']"

# Selector for individual transcript phrase spans.
# Each span carries: role="button", class contains "rc-Phrase",
# aria-label="play video from <spoken text>"
_PHRASE_SEL = "span.rc-Phrase[role='button']"

# Prefix that Coursera prepends to each phrase's aria-label
_ARIA_PREFIX = "play video from "

# Timeouts (seconds)
_PAGE_WAIT  = 15   # for the Transcript button to become clickable
_PANEL_WAIT = 15   # for phrase elements to appear after opening panel


def _slug_from_url(url: str) -> str:
    """
    Extract the human-readable slug at the end of a Coursera lecture URL.
    e.g. '.../lecture/gsIla/course-introductory-video' -> 'course-introductory-video'
    """
    return url.rstrip("/").split("/")[-1]


def _safe_filename(text: str, max_len: int = 80) -> str:
    """Turn arbitrary text into a filesystem-safe filename component."""
    slug = re.sub(r"[^\w\-]", "_", text)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:max_len]


def get_transcript(driver, lecture: dict, module_number: int) -> dict:
    """
    Navigate to a lecture page, open the Transcript panel if necessary,
    and extract the full transcript text.

    Parameters
    ----------
    driver         : Selenium WebDriver (reused across calls)
    lecture        : dict with keys 'title', 'url', 'type'
    module_number  : integer module index (carried into saved metadata)

    Returns
    -------
    dict:
        title         – lecture title
        url           – lecture URL
        module_number – integer
        slug          – URL slug used for filenames
        transcript    – cleaned transcript text (empty string if unavailable)
        status        – 'ok' | 'no_transcript' | 'error'
        error         – error description (only when status == 'error')
    """
    url   = lecture["url"]
    title = lecture["title"]
    slug  = _slug_from_url(url)

    result = {
        "title": title,
        "url": url,
        "module_number": module_number,
        "slug": slug,
        "transcript": "",
        "status": "no_transcript",
        "error": "",
    }

    # ── 1. Navigate ───────────────────────────────────────────────────────────
    driver.get(url)

    # ── 2. Wait for Transcript button ─────────────────────────────────────────
    try:
        btn = WebDriverWait(driver, _PAGE_WAIT).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, _BTN_TRANSCRIPT))
        )
    except TimeoutException:
        result["status"] = "error"
        result["error"]  = "Transcript button did not appear within timeout."
        return result

    # ── 3. Open the panel ONLY if it is currently closed ─────────────────────
    # Clicking a button that is aria-pressed="true" would close the panel.
    if btn.get_attribute("aria-pressed") != "true":
        btn.click()
        # Wait until the button confirms the panel is open
        try:
            WebDriverWait(driver, _PANEL_WAIT).until(
                lambda d: d.find_element(
                    By.CSS_SELECTOR, _BTN_TRANSCRIPT
                ).get_attribute("aria-pressed") == "true"
            )
        except TimeoutException:
            result["status"] = "error"
            result["error"]  = "Transcript panel did not open after click."
            return result

    # ── 4. Wait for phrase elements to appear inside the panel ────────────────
    # rc-Phrase spans are rendered once the panel content loads.
    try:
        WebDriverWait(driver, _PANEL_WAIT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, _PHRASE_SEL)
            )
        )
    except TimeoutException:
        # Panel is open but no phrase elements appeared — no transcript.
        result["status"] = "no_transcript"
        return result

    # ── 5. Extract text from every rc-Phrase span ─────────────────────────────
    # Each span's aria-label is: "play video from <spoken text>"
    # We strip the prefix to get the clean spoken sentence.
    try:
        phrases = driver.find_elements(By.CSS_SELECTOR, _PHRASE_SEL)
    except NoSuchElementException:
        result["status"] = "error"
        result["error"]  = "Phrase elements disappeared after wait."
        return result

    if not phrases:
        result["status"] = "no_transcript"
        return result

    lines = []
    for phrase in phrases:
        aria = phrase.get_attribute("aria-label") or ""
        if aria.startswith(_ARIA_PREFIX):
            text = aria[len(_ARIA_PREFIX):].strip()
            if text:
                lines.append(text)

    if not lines:
        # Phrases existed but none had readable aria-labels — treat as error
        result["status"] = "error"
        result["error"]  = (
            f"Found {len(phrases)} phrase elements but none had "
            "recognizable aria-label content."
        )
        return result

    # Join phrases with a space. Each line is a complete sentence/segment.
    transcript_text = " ".join(lines)

    result["transcript"] = transcript_text
    result["status"]     = "ok"
    return result


def save_transcript(result: dict, course_slug: str, output_dir: Path) -> Optional[Path]:
    """
    Save a transcript result to a UTF-8 text file.

    Path:
        <output_dir>/transcripts/<course_slug>/module_<NN>/<slug>.txt

    Header:
        Title:  <title>
        URL:    <url>
        Module: <module_number>
        ---
        <transcript text>

    If the file already exists, it is skipped (returns None) so reruns
    are safe.  Nothing is written when status != 'ok'.

    Returns the Path written, or None when skipped or not applicable.
    """
    if result["status"] != "ok" or not result["transcript"]:
        return None

    module_dir = (
        output_dir
        / "transcripts"
        / course_slug
        / f"module_{result['module_number']:02d}"
    )
    module_dir.mkdir(parents=True, exist_ok=True)

    filename  = _safe_filename(result["slug"]) + ".txt"
    file_path = module_dir / filename

    if file_path.exists():
        return None  # Skip — supports idempotent reruns

    content = (
        f"Title:  {result['title']}\n"
        f"URL:    {result['url']}\n"
        f"Module: {result['module_number']}\n"
        f"---\n\n"
        f"{result['transcript']}\n"
    )
    file_path.write_text(content, encoding="utf-8")
    return file_path
