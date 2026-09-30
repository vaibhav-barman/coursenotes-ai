"""
test_transcript.py  —  Phase 2 incremental test.

Tests transcript extraction on exactly 3 lectures from Modern Databases
Module 1, then saves them to output/transcripts/.

Run:
    cd src
    python test_transcript.py

Expected output:
    - Transcript button found and clicked for each lecture
    - Short preview (first 200 chars) and word count printed
    - Files saved under ../output/transcripts/modern-databases/module_01/
    - Graceful 'no_transcript' message for any lecture without a transcript
"""

import sys
from pathlib import Path

# Allow imports from src/ when running as 'cd src && python test_transcript.py'
sys.path.insert(0, str(Path(__file__).parent))

import browser
import coursera
import course
import transcript as tr

# ── Test sample ───────────────────────────────────────────────────────────────
# Three lectures from Module 1, Modern Databases.
# Using hardcoded URLs here to keep the test fast (no full module scrape).
# The slug at the end of each URL becomes the filename.

SAMPLE_LECTURES = [
    {
        "title": "Course Introductory Video",
        "url": "https://www.coursera.org/learn/modern-databases/lecture/gsIla/course-introductory-video",
        "type": "lecture",
    },
    {
        "title": "Meet Your Instructor - Prof. Pravin Y. Pawar",
        "url": "https://www.coursera.org/learn/modern-databases/lecture/3i3vG/meet-your-instructor-prof-pravin-y-pawar",
        "type": "lecture",
    },
    {
        "title": "Meet Your Instructor - Prof. Ashish Narang",
        "url": "https://www.coursera.org/learn/modern-databases/lecture/SGmZW/meet-your-instructor-prof-ashish-narang",
        "type": "lecture",
    },
]

COURSE_SLUG = "modern-databases"
MODULE_NUMBER = 1

# Output directory: project_root/output/
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# ── Run ───────────────────────────────────────────────────────────────────────
driver = browser.setup()

coursera.open_coursera(driver)

input("Press Enter when Coursera is ready (log in if needed)...")

print(f"\nTesting transcript extraction on {len(SAMPLE_LECTURES)} lectures.\n")

for i, lecture in enumerate(SAMPLE_LECTURES, 1):
    print(f"[{i}/{len(SAMPLE_LECTURES)}] {lecture['title']}")
    print(f"  URL: {lecture['url']}")

    result = tr.get_transcript(driver, lecture, MODULE_NUMBER)

    status = result["status"]

    if status == "ok":
        text = result["transcript"]
        words = len(text.split())
        chars = len(text)
        preview = text[:200].replace("\n", " ")
        print(f"  ✅ Status  : ok")
        print(f"  📊 Length  : {chars} chars / {words} words")
        print(f"  📝 Preview : {preview!r}")

        saved = tr.save_transcript(result, COURSE_SLUG, OUTPUT_DIR)
        if saved:
            print(f"  💾 Saved   : {saved}")
        else:
            print(f"  ⏭  Skipped  : file already exists")

    elif status == "no_transcript":
        print(f"  ⚠️  Status  : no transcript available for this lecture")

    else:
        print(f"  ❌ Status  : error — {result['error']}")

    print()

print("--- Test complete ---")
print(f"Output directory: {OUTPUT_DIR}/transcripts/{COURSE_SLUG}/")

input("\nPress Enter to close the browser...")
driver.quit()
