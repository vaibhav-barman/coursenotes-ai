from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_course_links(driver):

    print("Waiting for courses to load...")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located(
            (By.XPATH, "//a[contains(@href, '/learn/')]")
        )
    )

    print("Courses loaded.")

    links = driver.find_elements(
        By.XPATH,
        "//a[contains(@href, '/learn/')]"
    )

    courses = []
    seen_urls = set()

    for link in links:

        name = link.text.strip()
        url = link.get_attribute("href")

        if not name or not url:
            continue

        if "/home/welcome" not in url:
            continue

        if url in seen_urls:
            continue

        courses.append({
            "name": name,
            "url": url
        })

        seen_urls.add(url)

    return courses


def open_course(driver, course):
    driver.get(course["url"])


def get_modules(driver):
    """
    Read the module sidebar links from the currently open course home page.

    Coursera renders a left-hand sidebar with links in the form:
        /learn/{course-slug}/home/module/{n}

    We grab all of those, strip the anchor-fragment variants (the ones
    ending in #main that are only used for skip-navigation), and return
    them sorted by module number so we iterate in order later.

    Returns a list of dicts, each with:
        number  – integer module index extracted from the URL
        name    – link text, e.g. "Module 3" (falls back to "Module {n}")
        url     – fully-resolved absolute URL
    """
    print("Waiting for module sidebar to load...")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located(
            # Match sidebar module links; exclude the #main skip-nav variant
            (By.XPATH, "//a[contains(@href, '/home/module/') and not(contains(@href, '#'))]")
        )
    )

    raw_links = driver.find_elements(
        By.XPATH,
        "//a[contains(@href, '/home/module/') and not(contains(@href, '#'))]"
    )

    modules = []
    seen_urls = set()

    for link in raw_links:
        url = link.get_attribute("href") or ""
        name = link.text.strip()

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        # Extract the trailing integer, e.g. ".../home/module/5" -> 5
        # If the URL doesn't end in an integer we skip it; it's not a
        # numbered module page.
        try:
            number = int(url.rstrip("/").split("/")[-1])
        except ValueError:
            continue

        modules.append({
            "number": number,
            "name": name if name else f"Module {number}",
            "url": url,
        })

    # Sort in case the DOM doesn't list them in order
    modules.sort(key=lambda m: m["number"])

    return modules


def get_module_items(driver, module):
    """
    Navigate to a single module page and return its content items.

    We visit the module URL and wait for lecture or supplement links to
    appear. Items are returned as dicts with:
        title – cleaned title string (first non-empty line of the link text)
        url   – fully-resolved absolute URL
        type  – "lecture" for video links, "reading" for supplement links

    Discussion prompts, quizzes, graded assignments, and all other link
    types are intentionally excluded.

    If a module has no accessible content links (e.g. it is locked or
    genuinely empty), an empty list is returned rather than raising.
    """
    print(f"  Visiting Module {module['number']}: {module['name']}...")

    driver.get(module["url"])

    # Wait for either a lecture or supplement link to appear.
    # If neither appears within 15 s we treat the module as empty/locked.
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.XPATH,
                 "//a[contains(@href, '/lecture/') or contains(@href, '/supplement/')]")
            )
        )
    except Exception:
        print(f"    No content links found (module may be locked or empty).")
        return []

    raw_links = driver.find_elements(
        By.XPATH,
        "//a[contains(@href, '/lecture/') or contains(@href, '/supplement/')]"
    )

    items = []
    seen_urls = set()

    for link in raw_links:
        url = link.get_attribute("href") or ""
        text = link.text.strip()

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        # Determine content type from URL segment
        if "/lecture/" in url:
            item_type = "lecture"
        elif "/supplement/" in url:
            item_type = "reading"
        else:
            continue  # Shouldn't happen given the XPath, but be safe

        # The link text often contains the title on one line and a type
        # label on the next (e.g. "Course Intro\nVideo • 4 min").
        # We take only the first meaningful line as the title.
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0] if lines else "(no title)"

        items.append({
            "title": title,
            "url": url,
            "type": item_type,
        })

    return items