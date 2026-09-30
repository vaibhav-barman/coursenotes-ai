"""
test_pipeline.py — Unit tests for the resumable transcript extraction pipeline.

Uses unittest.mock to test pipeline control flow, retries, resume behavior,
error handling, and report generation without requiring a live browser.
"""

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src/ is importable
_src_dir = str(Path(__file__).parent.parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import pipeline
import transcript as tr


class TestPipelineHelpers(unittest.TestCase):
    def test_extract_course_slug(self):
        url1 = "https://www.coursera.org/learn/modern-databases/home/welcome"
        self.assertEqual(pipeline.extract_course_slug(url1), "modern-databases")

        url2 = "https://www.coursera.org/learn/cloud-computing"
        self.assertEqual(pipeline.extract_course_slug(url2), "cloud-computing")

        url3 = "https://www.coursera.org/learn/algorithms-part1/lecture/AbCdE/intro"
        self.assertEqual(pipeline.extract_course_slug(url3), "algorithms-part1")

        # Fallback
        url4 = "https://example.com/courses/my-course"
        self.assertEqual(pipeline.extract_course_slug(url4), "my-course")

    def test_get_transcript_path_and_is_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            course_slug = "test-course"
            mod_num = 1
            lecture_url = "https://coursera.org/learn/test-course/lecture/abc/test-lecture"

            path = tr.get_transcript_path(out_dir, course_slug, mod_num, lecture_url)
            self.assertEqual(
                path,
                out_dir / "transcripts" / "test-course" / "module_01" / "test-lecture.txt",
            )

            # Not created yet
            self.assertFalse(tr.is_transcript_saved(out_dir, course_slug, mod_num, lecture_url))

            # Created but empty (0 bytes)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            self.assertFalse(tr.is_transcript_saved(out_dir, course_slug, mod_num, lecture_url))

            # Created with content (>0 bytes)
            path.write_text("Spoken words here", encoding="utf-8")
            self.assertTrue(tr.is_transcript_saved(out_dir, course_slug, mod_num, lecture_url))


class TestExtractionRetries(unittest.TestCase):
    @patch("transcript.get_transcript")
    def test_success_on_first_attempt(self, mock_get):
        mock_get.return_value = {
            "title": "Intro",
            "url": "https://coursera.org/lecture/1",
            "module_number": 1,
            "slug": "intro",
            "transcript": "Hello world",
            "status": "ok",
            "error": "",
        }

        mock_driver = MagicMock()
        lecture = {"title": "Intro", "url": "https://coursera.org/lecture/1"}
        result = pipeline.extract_lecture_with_retry(mock_driver, lecture, 1, max_retries=2)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(mock_get.call_count, 1)

    @patch("time.sleep", return_value=None)
    @patch("transcript.get_transcript")
    def test_retry_on_transient_error_then_success(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            {"status": "error", "error": "Timeout opening panel", "title": "Intro", "url": "", "module_number": 1, "slug": "intro", "transcript": ""},
            {"status": "ok", "error": "", "title": "Intro", "url": "", "module_number": 1, "slug": "intro", "transcript": "Now it works"},
        ]

        mock_driver = MagicMock()
        lecture = {"title": "Intro", "url": "https://coursera.org/lecture/1"}
        result = pipeline.extract_lecture_with_retry(mock_driver, lecture, 1, max_retries=2, retry_delay=0.01)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch("transcript.get_transcript")
    def test_failure_exhausts_retries(self, mock_get, mock_sleep):
        mock_get.return_value = {
            "status": "error",
            "error": "Button never appeared",
            "title": "Intro",
            "url": "",
            "module_number": 1,
            "slug": "intro",
            "transcript": "",
        }

        mock_driver = MagicMock()
        lecture = {"title": "Intro", "url": "https://coursera.org/lecture/1"}
        # max_retries=2 means 1 initial attempt + 2 retries = 3 calls
        result = pipeline.extract_lecture_with_retry(mock_driver, lecture, 1, max_retries=2, retry_delay=0.01)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(mock_get.call_count, 3)
        self.assertIn("Failed after 3 attempts", result["error"])

    @patch("transcript.get_transcript")
    def test_no_transcript_does_not_retry(self, mock_get):
        mock_get.return_value = {
            "status": "no_transcript",
            "error": "",
            "title": "Silent Video",
            "url": "",
            "module_number": 1,
            "slug": "silent-video",
            "transcript": "",
        }

        mock_driver = MagicMock()
        lecture = {"title": "Silent Video", "url": "https://coursera.org/lecture/2"}
        result = pipeline.extract_lecture_with_retry(mock_driver, lecture, 1, max_retries=2)

        self.assertEqual(result["status"], "no_transcript")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(mock_get.call_count, 1)


class TestPipelineExecution(unittest.TestCase):
    def test_pipeline_control_flow_and_resumption(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            course_slug = "modern-databases"

            # Pre-save lecture 1 to simulate an existing transcript from previous run
            pre_saved_path = out_dir / "transcripts" / course_slug / "module_01" / "lecture-1.txt"
            pre_saved_path.parent.mkdir(parents=True, exist_ok=True)
            pre_saved_path.write_text("Existing transcript text", encoding="utf-8")

            # Mock items for 2 modules
            all_items = [
                {
                    "module": {"number": 1, "name": "Module 1", "url": "http://mod1"},
                    "items": [
                        {"title": "Lec 1", "url": "http://course/lecture/1/lecture-1", "type": "lecture"},
                        {"title": "Reading 1", "url": "http://course/reading/1", "type": "reading"},
                        {"title": "Lec 2", "url": "http://course/lecture/2/lecture-2", "type": "lecture"},
                    ],
                },
                {
                    "module": {"number": 2, "name": "Module 2", "url": "http://mod2"},
                    "items": [
                        {"title": "Lec 3", "url": "http://course/lecture/3/lecture-3", "type": "lecture"},
                        {"title": "Lec 4", "url": "http://course/lecture/4/lecture-4", "type": "lecture"},
                    ],
                },
            ]

            mock_driver = MagicMock()
            course_info = {
                "name": "Modern Databases",
                "url": f"https://www.coursera.org/learn/{course_slug}/home/welcome",
            }

            def fake_get_transcript(driver, lecture, mod_num):
                url = lecture["url"]
                slug = lecture["url"].split("/")[-1]
                if "lecture-2" in url:
                    # Successful extraction
                    return {
                        "title": lecture["title"],
                        "url": url,
                        "module_number": mod_num,
                        "slug": slug,
                        "transcript": "Fresh extracted transcript for lecture 2",
                        "status": "ok",
                        "error": "",
                    }
                elif "lecture-3" in url:
                    # No transcript available
                    return {
                        "title": lecture["title"],
                        "url": url,
                        "module_number": mod_num,
                        "slug": slug,
                        "transcript": "",
                        "status": "no_transcript",
                        "error": "",
                    }
                else:  # lecture-4
                    # Extraction error
                    return {
                        "title": lecture["title"],
                        "url": url,
                        "module_number": mod_num,
                        "slug": slug,
                        "transcript": "",
                        "status": "error",
                        "error": "Simulated extraction failure",
                    }

            with patch("transcript.get_transcript", side_effect=fake_get_transcript), \
                 patch("time.sleep", return_value=None):
                report = pipeline.extract_course_transcripts(
                    driver=mock_driver,
                    course_info=course_info,
                    all_items=all_items,
                    output_dir=out_dir,
                    max_retries=1,
                    retry_delay=0.01,
                    delay_between_lectures=0,
                )

            # Check summary counts
            summary = report["summary"]
            self.assertEqual(summary["total_lectures"], 4)
            self.assertEqual(summary["processed"], 4)
            self.assertEqual(summary["skipped"], 1)      # Lec 1 was pre-saved
            self.assertEqual(summary["completed"], 1)    # Lec 2
            self.assertEqual(summary["unavailable"], 1)  # Lec 3
            self.assertEqual(summary["failed"], 1)       # Lec 4

            # Verify order preservation in items
            item_titles = [item["lecture_title"] for item in report["items"]]
            self.assertEqual(item_titles, ["Lec 1", "Lec 2", "Lec 3", "Lec 4"])

            # Verify saved file for newly extracted lecture 2
            lec2_file = out_dir / "transcripts" / course_slug / "module_01" / "lecture-2.txt"
            self.assertTrue(lec2_file.exists())
            self.assertIn("Fresh extracted transcript", lec2_file.read_text(encoding="utf-8"))

            # Verify reports created in output_dir/reports
            reports_dir = out_dir / "reports"
            self.assertTrue(reports_dir.exists())
            report_files = list(reports_dir.glob(f"{course_slug}_transcript_report_*.json"))
            self.assertEqual(len(report_files), 1)

            latest_file = reports_dir / f"{course_slug}_latest.json"
            self.assertTrue(latest_file.exists())

            # Read back saved report
            saved_report = json.loads(latest_file.read_text(encoding="utf-8"))
            self.assertEqual(saved_report["summary"]["completed"], 1)
            self.assertEqual(len(saved_report["unavailable_lectures"]), 1)
            self.assertEqual(len(saved_report["failed_lectures"]), 1)

    def test_pipeline_graceful_interrupt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            course_slug = "modern-databases"

            all_items = [
                {
                    "module": {"number": 1, "name": "Module 1", "url": "http://mod1"},
                    "items": [
                        {"title": "Lec 1", "url": "http://course/lecture/1/lecture-1", "type": "lecture"},
                        {"title": "Lec 2", "url": "http://course/lecture/2/lecture-2", "type": "lecture"},
                    ],
                }
            ]

            mock_driver = MagicMock()
            course_info = {"name": "Course", "url": f"https://coursera.org/learn/{course_slug}"}

            def fake_get_transcript(driver, lecture, mod_num):
                if "lecture-1" in lecture["url"]:
                    return {
                        "title": lecture["title"],
                        "url": lecture["url"],
                        "module_number": mod_num,
                        "slug": "lecture-1",
                        "transcript": "Text 1",
                        "status": "ok",
                        "error": "",
                    }
                raise KeyboardInterrupt("Simulated Ctrl+C")

            with patch("transcript.get_transcript", side_effect=fake_get_transcript), \
                 patch("time.sleep", return_value=None):
                report = pipeline.extract_course_transcripts(
                    driver=mock_driver,
                    course_info=course_info,
                    all_items=all_items,
                    output_dir=out_dir,
                    delay_between_lectures=0,
                )

            self.assertEqual(report["status"], "interrupted")
            self.assertEqual(report["summary"]["completed"], 1)
            self.assertEqual(report["summary"]["processed"], 1)

            # Report was still saved
            reports_dir = out_dir / "reports"
            latest_file = reports_dir / f"{course_slug}_latest.json"
            self.assertTrue(latest_file.exists())


if __name__ == "__main__":
    unittest.main()
