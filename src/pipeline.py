"""
pipeline.py  —  Phase 2: Resumable course-wide transcript extraction.

Orchestrates course discovery, module discovery, and lecture transcript
extraction with:
  - Idempotent execution (skips already saved transcripts to resume safely)
  - Bounded retries for transient navigation/browser errors
  - Graceful interrupt handling (preserves progress and report on Ctrl+C)
  - Detailed machine-readable JSON run report under output/reports/
  - Strict preservation of course, module, and lecture order
"""

import sys
import re
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure src/ is importable regardless of launch directory
_src_dir = str(Path(__file__).parent.resolve())
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import browser
import coursera
import course
import transcript as tr


def extract_course_slug(course_url: str) -> str:
    """
    Extract the course slug from a Coursera URL.
    e.g. 'https://www.coursera.org/learn/modern-databases/home/welcome' -> 'modern-databases'
         'https://www.coursera.org/learn/cloud-computing' -> 'cloud-computing'
    """
    match = re.search(r"/learn/([^/?#]+)", course_url)
    if match:
        return match.group(1)
    parts = [p for p in course_url.rstrip("/").split("/") if p and p not in ("home", "welcome")]
    return parts[-1] if parts else "course"


def extract_lecture_with_retry(
    driver,
    lecture: Dict[str, Any],
    module_number: int,
    max_retries: int = 2,
    retry_delay: float = 2.0,
) -> Dict[str, Any]:
    """
    Extract the transcript for a lecture with bounded retries for transient failures.

    Does NOT retry if extraction returns 'ok' or 'no_transcript'.
    Retries only on 'error' status or unexpected WebDriver/navigation exceptions.
    """
    last_error = ""
    for attempt in range(1, max_retries + 2):
        try:
            result = tr.get_transcript(driver, lecture, module_number)
            if result.get("status") in ("ok", "no_transcript"):
                result["attempts"] = attempt
                return result
            last_error = result.get("error", "Unknown extraction error")
        except Exception as exc:
            last_error = str(exc)
            result = {
                "title": lecture.get("title", ""),
                "url": lecture.get("url", ""),
                "module_number": module_number,
                "slug": tr.slug_from_url(lecture.get("url", "")),
                "transcript": "",
                "status": "error",
                "error": last_error,
            }

        if attempt <= max_retries:
            print(f"    ⚠️  Attempt {attempt} failed: {last_error}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)

    result["attempts"] = max_retries + 1
    result["status"] = "error"
    result["error"] = f"Failed after {max_retries + 1} attempts: {last_error}"
    return result


def save_run_report(
    report_data: Dict[str, Any],
    output_dir: Path,
    course_slug: str,
) -> Path:
    """
    Save run statistics and item outcomes to a timestamped JSON file
    and update the latest report pointer in <output_dir>/reports/.
    """
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"{course_slug}_transcript_report_{timestamp_str}.json"
    latest_file = reports_dir / f"{course_slug}_latest.json"

    json_content = json.dumps(report_data, indent=2, ensure_ascii=False)
    report_file.write_text(json_content, encoding="utf-8")
    latest_file.write_text(json_content, encoding="utf-8")

    return report_file


def extract_course_transcripts(
    driver,
    course_info: Dict[str, Any],
    all_items: Optional[List[Dict[str, Any]]] = None,
    output_dir: Optional[Path] = None,
    max_retries: int = 2,
    retry_delay: float = 2.0,
    delay_between_lectures: float = 1.0,
    module_filter: Optional[List[int]] = None,
    limit_lectures: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run course-wide transcript extraction.

    Parameters
    ----------
    driver : Selenium WebDriver
    course_info : dict with 'name' and 'url'
    all_items : optional pre-discovered items structure from course.get_module_items
    output_dir : root output Path (defaults to project_root/output)
    max_retries : retry count for transient navigation/extraction errors
    retry_delay : delay in seconds between retries
    delay_between_lectures : delay in seconds between live lecture requests
    module_filter : optional list of module numbers to process (e.g. [1, 2])
    limit_lectures : optional max count of lectures to process (for testing)

    Returns
    -------
    dict : comprehensive run report with summary and item-level details
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "output"

    course_slug = extract_course_slug(course_info.get("url", ""))
    course_name = course_info.get("name", course_slug)

    print("\n" + "=" * 64)
    print(f"  RESUMABLE TRANSCRIPT EXTRACTION")
    print(f"  Course: {course_name} ({course_slug})")
    print("=" * 64)

    # 1. Discover modules and lecture items if not pre-provided
    if all_items is None:
        course.open_course(driver, course_info)
        modules = course.get_modules(driver)
        if module_filter:
            modules = [m for m in modules if m["number"] in module_filter]

        all_items = []
        for mod in modules:
            items = course.get_module_items(driver, mod)
            all_items.append({"module": mod, "items": items})
    elif module_filter:
        all_items = [b for b in all_items if b["module"]["number"] in module_filter]

    # Calculate total lectures across selected modules
    total_lectures_target = sum(
        len([i for i in block["items"] if i.get("type") == "lecture"])
        for block in all_items
    )

    if limit_lectures:
        total_lectures_target = min(total_lectures_target, limit_lectures)

    print(f"\nTarget: {len(all_items)} module(s), {total_lectures_target} lecture(s).")
    print(f"Output directory: {output_dir / 'transcripts' / course_slug}\n")

    summary = {
        "total_modules": len(all_items),
        "total_lectures": total_lectures_target,
        "processed": 0,
        "completed": 0,
        "skipped": 0,
        "unavailable": 0,
        "failed": 0,
    }

    report_items = []
    module_summaries = []
    unavailable_lectures = []
    failed_lectures = []

    start_time = datetime.now()
    run_status = "completed"
    lectures_seen = 0

    try:
        for block in all_items:
            mod = block["module"]
            mod_num = mod["number"]
            mod_name = mod.get("name", f"Module {mod_num}")
            lectures = [i for i in block["items"] if i.get("type") == "lecture"]

            mod_summary = {
                "module_number": mod_num,
                "module_name": mod_name,
                "total_lectures": len(lectures),
                "completed": 0,
                "skipped": 0,
                "unavailable": 0,
                "failed": 0,
            }

            print(f"\n--- [Module {mod_num:02d}: {mod_name}] ({len(lectures)} lectures) ---")

            for lec_idx, lecture in enumerate(lectures, 1):
                if limit_lectures and lectures_seen >= limit_lectures:
                    break

                lectures_seen += 1
                title = lecture.get("title", "(untitled)")
                url = lecture.get("url", "")
                slug = tr.slug_from_url(url)

                print(f"[{lectures_seen}/{total_lectures_target}] {title}")
                print(f"  URL: {url}")

                # Check if already saved (resumability)
                if tr.is_transcript_saved(output_dir, course_slug, mod_num, url):
                    saved_path = tr.get_transcript_path(output_dir, course_slug, mod_num, url)
                    print(f"  ⏭  Skipped  : already saved ({saved_path.name})")

                    item_record = {
                        "module_number": mod_num,
                        "module_name": mod_name,
                        "lecture_title": title,
                        "lecture_url": url,
                        "slug": slug,
                        "status": "skipped",
                        "error": "",
                        "char_count": 0,
                        "word_count": 0,
                        "saved_path": str(saved_path),
                        "attempts": 0,
                    }
                    report_items.append(item_record)
                    summary["skipped"] += 1
                    mod_summary["skipped"] += 1
                    summary["processed"] += 1
                    continue

                # Live extraction with bounded retry
                result = extract_lecture_with_retry(
                    driver,
                    lecture,
                    mod_num,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                )

                status = result.get("status")
                item_record = {
                    "module_number": mod_num,
                    "module_name": mod_name,
                    "lecture_title": title,
                    "lecture_url": url,
                    "slug": slug,
                    "status": status,
                    "error": result.get("error", ""),
                    "char_count": 0,
                    "word_count": 0,
                    "saved_path": "",
                    "attempts": result.get("attempts", 1),
                }

                if status == "ok":
                    text = result.get("transcript", "")
                    words = len(text.split())
                    chars = len(text)
                    item_record["char_count"] = chars
                    item_record["word_count"] = words

                    saved_path = tr.save_transcript(result, course_slug, output_dir)
                    item_record["saved_path"] = str(saved_path) if saved_path else ""

                    print(f"  ✅ Status   : ok ({chars:,} chars / {words:,} words)")
                    if saved_path:
                        print(f"  💾 Saved    : {saved_path}")

                    summary["completed"] += 1
                    mod_summary["completed"] += 1

                elif status == "no_transcript":
                    print("  ⚠️  Status   : no transcript available on Coursera")
                    summary["unavailable"] += 1
                    mod_summary["unavailable"] += 1
                    unavailable_lectures.append({
                        "module_number": mod_num,
                        "module_name": mod_name,
                        "lecture_title": title,
                        "lecture_url": url,
                    })

                else:  # status == "error"
                    print(f"  ❌ Status   : failed — {result.get('error')}")
                    summary["failed"] += 1
                    mod_summary["failed"] += 1
                    failed_lectures.append({
                        "module_number": mod_num,
                        "module_name": mod_name,
                        "lecture_title": title,
                        "lecture_url": url,
                        "error": result.get("error", ""),
                        "attempts": result.get("attempts", 1),
                    })

                summary["processed"] += 1
                report_items.append(item_record)

                if delay_between_lectures > 0:
                    time.sleep(delay_between_lectures)

            module_summaries.append(mod_summary)
            if limit_lectures and lectures_seen >= limit_lectures:
                break

    except KeyboardInterrupt:
        print("\n\n⚠️  Extraction interrupted by user (Ctrl+C). Saving partial progress...")
        run_status = "interrupted"

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    report_data = {
        "course_name": course_name,
        "course_slug": course_slug,
        "course_url": course_info.get("url", ""),
        "run_timestamp": start_time.isoformat(),
        "completion_timestamp": end_time.isoformat(),
        "duration_seconds": round(duration, 2),
        "status": run_status,
        "summary": summary,
        "modules": module_summaries,
        "items": report_items,
        "unavailable_lectures": unavailable_lectures,
        "failed_lectures": failed_lectures,
    }

    report_path = save_run_report(report_data, output_dir, course_slug)

    # Print summary block
    print("\n" + "=" * 64)
    print("              TRANSCRIPT EXTRACTION REPORT")
    print("=" * 64)
    print(f"Course       : {course_name} ({course_slug})")
    print(f"Status       : {run_status.upper()}")
    print(f"Duration     : {int(duration // 60)}m {int(duration % 60)}s")
    print("-" * 64)
    print(f"Modules      : {summary['total_modules']}")
    print(f"Target Total : {summary['total_lectures']} lectures")
    print(f"Processed    : {summary['processed']}")
    print(f"  ✅ Completed   : {summary['completed']:>4} (newly extracted & saved)")
    print(f"  ⏭  Skipped     : {summary['skipped']:>4} (already saved from previous run)")
    print(f"  ⚠️  Unavailable : {summary['unavailable']:>4} (no transcript on Coursera)")
    print(f"  ❌ Failed      : {summary['failed']:>4} (extraction errors)")
    print("-" * 64)
    print(f"Report saved to : {report_path}")
    print("=" * 64 + "\n")

    return report_data


def main():
    """Standalone entry point for transcript extraction."""
    driver = browser.setup()
    coursera.open_coursera(driver)

    input("Press Enter when Coursera is ready (log in if needed)...")

    courses = course.get_course_links(driver)
    if not courses:
        print("No enrolled courses found.")
        driver.quit()
        return

    print("\nEnrolled Courses:")
    for idx, c in enumerate(courses, 1):
        print(f"  [{idx}] {c['name']} ({c['url']})")

    selected_course = courses[0]
    print(f"\nSelected course: {selected_course['name']}")

    try:
        extract_course_transcripts(driver, selected_course)
    finally:
        input("\nPress Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    main()
