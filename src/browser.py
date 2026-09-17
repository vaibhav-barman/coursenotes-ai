from selenium import webdriver
from pathlib import Path


def setup():
    options = webdriver.ChromeOptions()

    profile_path = Path(__file__).parent.parent / "browser_data"
    options.add_argument(f"--user-data-dir={profile_path}")

    driver = webdriver.Chrome(options=options)

    return driver