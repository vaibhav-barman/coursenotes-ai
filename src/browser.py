from selenium import webdriver
from pathlib import Path


def setup():
    print("Starting browser...")

    options = webdriver.ChromeOptions()

    profile_path = Path(__file__).parent.parent / "browser_data"

    print(f"Browser profile: {profile_path}")

    options.add_argument(f"--user-data-dir={profile_path}")

    options.page_load_strategy = "eager"

    print("Launching Chrome...")

    driver = webdriver.Chrome(options=options)

    print("Chrome launched.")

    return driver