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