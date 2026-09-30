# Coursenotes AI

A Python project that automates the collection of course information from Coursera and works toward turning accessible lecture transcripts into structured study notes.

The project is under active development. Features are being built incrementally and are documented honestly below — implemented features are distinguished from planned ones.

---

## Current Features

The following features are **implemented and tested**:

- **Browser automation** — Launches Google Chrome with a persistent profile using Selenium, so login sessions are preserved across runs.
- **Course discovery** — Navigates to Coursera and discovers all enrolled courses dynamically. Does not hardcode course names or URLs.
- **Module and lecture discovery** — Opens an individual course and visits each module page to collect lecture titles, URLs, and supplementary reading links. Filters out quizzes, discussion prompts, assignments, and other non-content links.
- **Output verified for Modern Databases** — 12 modules, 186 lectures, and 53 supplementary readings discovered in a real authenticated session.

The following feature is **in development and not yet verified**:

- **Transcript extraction** *(experimental)* — Implementation exists in `src/transcript.py` to click the Coursera Transcript tab on a lecture page and extract its text. This has not yet been successfully tested end-to-end.

---

## Planned Roadmap

In order of implementation priority:

1. ✅ Discover enrolled courses
2. ✅ Discover modules, lectures, and supplementary readings
3. 🔄 Extract available lecture transcripts *(in progress)*
4. ⬜ Clean and normalize transcript text
5. ⬜ Generate structured study notes using an LLM
6. ⬜ Export notes to Markdown files
7. ⬜ Optional PDF export
8. ⬜ Organize output by course, module, and lecture
9. ⬜ Skip already-processed lectures on reruns
10. ⬜ Improve error handling, logging, and test coverage

---

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.9 |
| Browser automation | [Selenium](https://www.selenium.dev/) 4.x |
| Browser | Google Chrome (with ChromeDriver) |
| Session management | Persistent Chrome profile (`browser_data/`) |
| Dependencies | `requirements.txt` |

No LLM integration, PDF library, or external API is used yet.

---

## Prerequisites

- Python **3.9** or compatible
- **Google Chrome** installed
- **ChromeDriver** matching your Chrome version (Selenium 4 manages this automatically via Selenium Manager)
- **Git**

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/vaibhav-barman/coursenotes-ai.git
cd coursenotes-ai
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Authentication

The project uses a **persistent Chrome profile** stored in `browser_data/` at the project root. On first run, Chrome will open and you can log in to Coursera manually. Subsequent runs reuse the saved session automatically.

> **Important:** Never commit the `browser_data/` directory. It contains your browser session, cookies, and credentials. It is excluded from Git via `.gitignore`.

---

## Usage

Run the main script from the `src/` directory:

```bash
cd src
python main.py
```

The script will:

1. Launch Chrome using the persistent profile.
2. Open Coursera — log in manually if prompted, then press **Enter** in the terminal.
3. Discover all enrolled courses and print their names and URLs.
4. Open the first course (currently Modern Databases).
5. Discover all modules and visit each one to collect lecture and reading links.
6. Print a summary of modules, lectures, and readings found.

---

## Project Structure

```
coursenotes-ai/
├── src/
│   ├── main.py          # Entry point: runs the full discovery flow
│   ├── browser.py       # Chrome setup with persistent profile
│   ├── coursera.py      # Coursera homepage navigation
│   ├── course.py        # Course, module, and lecture discovery
│   └── transcript.py    # Transcript extraction (experimental, not yet verified)
├── output/              # Generated output — not committed (see .gitignore)
│   └── transcripts/     # Saved transcript text files (when implemented)
├── browser_data/        # Persistent Chrome profile — never commit this
├── tests/               # Test directory (currently empty)
├── requirements.txt     # Python dependencies
└── .gitignore
```

`notes/`, `transcripts/`, and `output/` at the project root are local output directories excluded from version control.

---

## Output and Git Hygiene

The following are **excluded from Git** and must never be committed:

| Path | Reason |
|---|---|
| `browser_data/` | Contains your browser session, cookies, and credentials |
| `.venv/` | Python virtual environment |
| `output/` | Generated transcript and note files |
| `src/*.html` | Temporary DOM inspection dumps |
| `.env` | Environment variables and API keys (not yet used) |

Generated course transcripts are copyrighted material and must not be shared in a public repository.

---

## Responsible Use

This project uses your **authorized Coursera account session** via a normal browser window. It only accesses content you are enrolled in and permitted to view.

You must not use this project to:

- Access content you are not authorized to view
- Bypass authentication, paywalls, or access restrictions
- Submit quizzes, assignments, or graded assessments
- Redistribute or republish course content

Use this project only for personal study assistance on content you have legitimately enrolled in.

---

## Known Limitations

- Only the first discovered course (Modern Databases) is processed in the current implementation. Multi-course support is planned.
- Transcript extraction has been partially implemented but **has not yet been successfully tested end-to-end**. The feature is marked experimental.
- There are no automated tests. The `tests/` directory exists but is empty.
- The project uses a `urllib3` / LibreSSL compatibility warning on macOS with Python 3.9. This does not affect functionality.
- Page load behavior depends on `page_load_strategy = "eager"` in `browser.py`. Some Coursera pages may still require brief waits for dynamic content.

---

## License

This project does not currently include a license file. All rights reserved by the author unless a license is added.
